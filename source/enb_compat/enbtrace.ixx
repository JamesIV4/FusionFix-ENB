module;

#include <common.hxx>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <unordered_map>
#include <unordered_set>

export module enbtrace;

import common;
import comvars;
import enbcompat;

// D3D9 instrumentation for the ENB compatibility investigation.
//
// Answers the questions Phase 2 of the plan needs answered: which shaders the
// game creates and what their bytecode hashes are, which constant registers and
// sampler stages each side of the FusionFix/ENB overlap actually touches, and
// which render targets exist at each point in the frame.
//
// Entirely opt-in and off by default. It is a diagnostic, not a fix: no call is
// altered, every hook forwards to the original.
//
// Hooking method: the device's vtable is swapped, not inline-patched. That
// composes predictably with ENBSeries -- our thunk calls the stored original
// pointer, which still lands inside ENB's own hook if it has one -- and it
// leaves the d3d9.dll export addresses alone, so whichever wrapper is loaded
// keeps working. See research/proxy-chain-results.md.

namespace ENBTrace
{
    // --- CRC32 ----------------------------------------------------------
    //
    // Standard reflected IEEE CRC32, matching zlib. Deliberately the same
    // function the offline tools use so a runtime dump and a static .fxc dump
    // can be joined on the hash: see tools/shader_dump/d3d9bc.py.

    const std::array<uint32_t, 256>& Crc32Table()
    {
        static const auto table = []
        {
            std::array<uint32_t, 256> t{};
            for (uint32_t i = 0; i < 256; ++i)
            {
                uint32_t c = i;
                for (int k = 0; k < 8; ++k)
                    c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
                t[i] = c;
            }
            return t;
        }();
        return table;
    }

    uint32_t Crc32(const uint8_t* data, size_t size)
    {
        auto& table = Crc32Table();
        uint32_t c = 0xFFFFFFFFu;
        for (size_t i = 0; i < size; ++i)
            c = table[(c ^ data[i]) & 0xFF] ^ (c >> 8);
        return c ^ 0xFFFFFFFFu;
    }

    // --- D3D9 bytecode --------------------------------------------------

    constexpr uint32_t kEndToken = 0x0000FFFFu;
    constexpr uint32_t kCommentId = 0x0000FFFEu;

    size_t ShaderTokenCount(const DWORD* function)
    {
        if (!function)
            return 0;
        size_t i = 1; // skip version token
        for (;;)
        {
            auto token = function[i];
            if (token == kEndToken)
                return i + 1;
            if ((token & 0xFFFFu) == kCommentId)
                i += 1 + ((token >> 16) & 0x7FFF);
            else
                i += 1 + ((token >> 24) & 0x0F);
            if (i > 0x40000) // runaway guard: no D3D9 shader is a megabyte long
                return 0;
        }
    }

    // The blob with comment blocks (CTAB, source file names) removed. Two
    // shaders that differ only in the compiler stamp inside their CTAB are the
    // same shader, so this is what gets hashed for identity.
    std::vector<DWORD> StripComments(const DWORD* function, size_t tokens)
    {
        std::vector<DWORD> out;
        if (!tokens)
            return out;
        out.reserve(tokens);
        out.push_back(function[0]);
        for (size_t i = 1; i < tokens;)
        {
            auto token = function[i];
            if (token == kEndToken)
            {
                out.push_back(token);
                break;
            }
            size_t length;
            if ((token & 0xFFFFu) == kCommentId)
            {
                i += 1 + ((token >> 16) & 0x7FFF);
                continue;
            }
            length = (token >> 24) & 0x0F;
            out.insert(out.end(), function + i, function + i + 1 + length);
            i += 1 + length;
        }
        return out;
    }

    // The "FusionShader" marker the FusionShaders build injects as def c219
    // (pixel) / def c230 (vertex). Present means this blob came from the
    // FusionFix replacement package rather than the stock game.
    bool HasFusionSignature(const DWORD* function, size_t tokens)
    {
        static const char marker[] = "FusionShader";
        auto bytes = reinterpret_cast<const char*>(function);
        auto size = tokens * sizeof(DWORD);
        if (size < sizeof(marker))
            return false;
        for (size_t i = 0; i + sizeof(marker) - 1 <= size; ++i)
        {
            if (std::memcmp(bytes + i, marker, sizeof(marker) - 1) == 0)
                return true;
        }
        return false;
    }

    // --- configuration --------------------------------------------------

    struct Config
    {
        bool enabled = false;
        bool dumpShaders = false;       // write .cso blobs to the dump directory
        bool traceDraws = false;        // per-draw lines; very heavy
        bool traceResources = true;     // Create*/SetRenderTarget/SetDepthStencilSurface
        bool traceTextures = false;     // every SetTexture
        bool traceConstants = false;    // every Set*ShaderConstantF
        bool traceShaderBinds = false;  // every SetPixelShader, by creation hash
        int startFrame = 0;             // first frame to trace
        int frameCount = 3;             // frames to trace once triggered
        int traceKey = 0;               // virtual-key that arms a capture; 0 = use startFrame
    };

    Config& Cfg()
    {
        static Config cfg;
        return cfg;
    }

    std::filesystem::path DumpDir()
    {
        return GetExeModulePath() / L"ENBCompat";
    }

    // --- output ---------------------------------------------------------

    std::mutex& OutMutex()
    {
        static std::mutex m;
        return m;
    }

    std::ofstream& TraceFile()
    {
        static std::ofstream file = []
        {
            std::error_code ec;
            std::filesystem::create_directories(DumpDir(), ec);
            return std::ofstream(DumpDir() / L"d3d9_trace.log", std::ios::trunc);
        }();
        return file;
    }

    std::ofstream& ShaderIndexFile()
    {
        static std::ofstream file = []
        {
            std::error_code ec;
            std::filesystem::create_directories(DumpDir(), ec);
            std::ofstream f(DumpDir() / L"shaders.csv", std::ios::trunc);
            f << "stage,crc32,crc32_stripped,tokens,bytes,fusion_signature,frame\n";
            return f;
        }();
        return file;
    }

    std::ofstream& FirstBindFile()
    {
        static std::ofstream file = []
        {
            std::error_code ec;
            std::filesystem::create_directories(DumpDir(), ec);
            std::ofstream f(DumpDir() / L"shader_first_binds.csv", std::ios::trunc);
            f << "stage,crc32,crc32_stripped,first_frame\n";
            return f;
        }();
        return file;
    }

    // --- state ----------------------------------------------------------

    std::atomic<int> gFrame{ 0 };
    std::atomic<bool> gInstalled{ false };

    // Which constant registers each stage has been written to, and which
    // sampler stages have been bound. Accumulated for the whole run and dumped
    // at shutdown: a summary answers "do FusionFix and ENB fight over a
    // register or a stage" without a per-call flood.
    std::array<bool, 256> gPixelConstants{};
    std::array<bool, 256> gVertexConstants{};
    std::array<bool, 16> gSamplerStages{};

    std::unordered_set<uint32_t>& SeenShaders()
    {
        static std::unordered_set<uint32_t> seen;
        return seen;
    }

    // Shader object -> the comment-stripped CRC32 of the bytecode it was created
    // from. Needed because SetPixelShader only hands over an opaque interface
    // pointer, and the question worth answering -- which of a container's many
    // compiled variants is actually bound for a given draw -- can only be
    // answered by tracing that pointer back to the bytecode.
    //
    // The hash is the same one tools/shader_dump/d3d9bc.py computes, so a bind
    // logged here can be looked up directly in a dumped shader set.
    std::unordered_map<void*, uint32_t>& ShaderHashes()
    {
        static std::unordered_map<void*, uint32_t> hashes;
        return hashes;
    }

    // Keep the raw hash as well as the comment-stripped identity. The former
    // identifies an assembled shaderinput replacement byte-for-byte; the latter
    // remains stable when only compiler/comment metadata differs.
    std::unordered_map<void*, uint32_t>& ShaderRawHashes()
    {
        static std::unordered_map<void*, uint32_t> hashes;
        return hashes;
    }

    std::unordered_set<uint64_t>& FirstBoundShaders()
    {
        static std::unordered_set<uint64_t> shaders;
        return shaders;
    }

    std::atomic<uint32_t> gCurrentPS{ 0 };
    std::atomic<uint32_t> gCurrentVS{ 0 };

    // Frame at which an armed capture stops. -1 means no capture is running.
    std::atomic<int> gCaptureUntil{ -1 };

    bool Tracing()
    {
        auto& cfg = Cfg();
        auto frame = gFrame.load(std::memory_order_relaxed);
        if (cfg.traceKey)
            return frame < gCaptureUntil.load(std::memory_order_relaxed);
        return frame >= cfg.startFrame && frame < cfg.startFrame + cfg.frameCount;
    }

    void Write(std::string_view line)
    {
        std::scoped_lock lock(OutMutex());
        auto& file = TraceFile();
        if (file)
            file << '[' << gFrame.load(std::memory_order_relaxed) << "] " << line << '\n';
    }

    // Arms a capture on a fresh key press.
    //
    // A frame-number window is useless for "capture this, then walk somewhere
    // and capture that", which is exactly the comparison the investigation
    // needs, so a key press decides when instead. Polled once per frame from
    // Present, and edge-triggered so holding the key captures once.
    void PollCaptureKey()
    {
        auto key = Cfg().traceKey;
        if (!key)
            return;

        static bool wasDown = false;
        auto isDown = (GetAsyncKeyState(key) & 0x8000) != 0;
        if (isDown && !wasDown && gCaptureUntil.load(std::memory_order_relaxed) < 0)
        {
            auto frame = gFrame.load(std::memory_order_relaxed);
            gCaptureUntil.store(frame + std::max(Cfg().frameCount, 1), std::memory_order_relaxed);
            Write("---- capture armed ----");
        }
        wasDown = isDown;

        auto until = gCaptureUntil.load(std::memory_order_relaxed);
        if (until >= 0 && gFrame.load(std::memory_order_relaxed) >= until)
        {
            Write("---- capture ended ----");
            gCaptureUntil.store(-1, std::memory_order_relaxed);
            std::scoped_lock lock(OutMutex());
            if (auto& file = TraceFile())
                file.flush();
        }
    }

    const char* FormatName(D3DFORMAT format)
    {
        switch (format)
        {
        case D3DFMT_A8R8G8B8:      return "A8R8G8B8";
        case D3DFMT_X8R8G8B8:      return "X8R8G8B8";
        case D3DFMT_A2B10G10R10:   return "A2B10G10R10";
        case D3DFMT_A16B16G16R16:  return "A16B16G16R16";
        case D3DFMT_A16B16G16R16F: return "A16B16G16R16F";
        case D3DFMT_A32B32G32R32F: return "A32B32G32R32F";
        case D3DFMT_G16R16:        return "G16R16";
        case D3DFMT_G16R16F:       return "G16R16F";
        case D3DFMT_R16F:          return "R16F";
        case D3DFMT_R32F:          return "R32F";
        case D3DFMT_L8:            return "L8";
        case D3DFMT_A8:            return "A8";
        case D3DFMT_D24S8:         return "D24S8";
        case D3DFMT_D24X8:         return "D24X8";
        case D3DFMT_D16:           return "D16";
        case D3DFMT_D32:           return "D32";
        default:                   return nullptr;
        }
    }

    std::string FormatString(D3DFORMAT format)
    {
        if (auto name = FormatName(format))
            return name;
        std::ostringstream out;
        out << "fmt" << static_cast<uint32_t>(format);
        return out.str();
    }

    std::string SurfaceDescription(IDirect3DSurface9* surface)
    {
        if (!surface)
            return "null";
        D3DSURFACE_DESC desc{};
        if (FAILED(surface->GetDesc(&desc)))
            return "?";
        std::ostringstream out;
        out << desc.Width << 'x' << desc.Height << ' ' << FormatString(desc.Format);
        if (desc.MultiSampleType != D3DMULTISAMPLE_NONE)
            out << " msaa" << static_cast<uint32_t>(desc.MultiSampleType);
        return out.str();
    }

    // --- shader fingerprinting ------------------------------------------

    uint32_t RecordShader(const char* stage, const DWORD* function, uint32_t* rawOut = nullptr)
    {
        auto tokens = ShaderTokenCount(function);
        if (!tokens)
            return 0;

        auto bytes = tokens * sizeof(DWORD);
        auto raw = Crc32(reinterpret_cast<const uint8_t*>(function), bytes);
        if (rawOut)
            *rawOut = raw;
        auto stripped = StripComments(function, tokens);
        auto strippedCrc = Crc32(reinterpret_cast<const uint8_t*>(stripped.data()),
                                 stripped.size() * sizeof(DWORD));
        auto fusion = HasFusionSignature(function, tokens);

        std::scoped_lock lock(OutMutex());
        if (!SeenShaders().insert(raw).second)
            return strippedCrc;

        auto& index = ShaderIndexFile();
        if (index)
        {
            index << stage << ',' << std::hex << std::uppercase << std::setfill('0')
                  << std::setw(8) << raw << ',' << std::setw(8) << strippedCrc
                  << std::dec << std::nouppercase << std::setfill(' ')
                  << ',' << tokens << ',' << bytes << ',' << (fusion ? 1 : 0)
                  << ',' << gFrame.load(std::memory_order_relaxed) << '\n';
            index.flush();
        }

        if (Cfg().dumpShaders)
        {
            std::error_code ec;
            auto dir = DumpDir() / L"shaders";
            std::filesystem::create_directories(dir, ec);
            std::ostringstream name;
            name << stage << '_' << std::hex << std::uppercase << std::setfill('0')
                 << std::setw(8) << raw << ".cso";
            std::ofstream out(dir / name.str(), std::ios::binary);
            if (out)
                out.write(reinterpret_cast<const char*>(function), bytes);
        }

        return strippedCrc;
    }

    // --- vtable hook ----------------------------------------------------
    //
    // Indices into the IDirect3DDevice9 vtable, in COM declaration order.

    enum Slot : size_t
    {
        Slot_Reset = 16,
        Slot_Present = 17,
        Slot_CreateTexture = 23,
        Slot_CreateRenderTarget = 28,
        Slot_CreateDepthStencilSurface = 29,
        Slot_EndScene = 42,
        Slot_SetRenderTarget = 37,
        Slot_SetDepthStencilSurface = 39,
        Slot_SetTexture = 65,
        Slot_SetSamplerState = 69,
        Slot_DrawPrimitive = 81,
        Slot_DrawIndexedPrimitive = 82,
        Slot_CreateVertexShader = 91,
        Slot_SetVertexShader = 92,
        Slot_SetVertexShaderConstantF = 94,
        Slot_CreatePixelShader = 106,
        Slot_SetPixelShader = 107,
        Slot_SetPixelShaderConstantF = 109,
        Slot_Count = 119,
    };

    std::array<void*, Slot_Count> gOriginal{};

    template <typename Fn>
    Fn Original(Slot slot)
    {
        return reinterpret_cast<Fn>(gOriginal[slot]);
    }

    // The frame boundary.
    //
    // Not Present: GTA IV presents through the swap chain, not the device, so a
    // device-vtable hook on Present never fires and a frame counter driven from
    // it stays at zero forever. EndScene is called on the device once per frame
    // by definition, so that is what drives the counter; this hook only records
    // whether Present is used at all.
    void AdvanceFrame()
    {
        gFrame.fetch_add(1, std::memory_order_relaxed);
        PollCaptureKey();
    }

    HRESULT WINAPI Hook_Present(IDirect3DDevice9* device, const RECT* src, const RECT* dst,
                                HWND window, const RGNDATA* dirty)
    {
        static std::once_flag once;
        std::call_once(once, [] { Write("IDirect3DDevice9::Present is in use"); });
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, const RECT*, const RECT*, HWND, const RGNDATA*);
        return Original<Fn>(Slot_Present)(device, src, dst, window, dirty);
    }

    HRESULT WINAPI Hook_EndScene(IDirect3DDevice9* device)
    {
        AdvanceFrame();
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*);
        return Original<Fn>(Slot_EndScene)(device);
    }

    HRESULT WINAPI Hook_Reset(IDirect3DDevice9* device, D3DPRESENT_PARAMETERS* params)
    {
        if (params)
        {
            std::ostringstream out;
            out << "Reset " << params->BackBufferWidth << 'x' << params->BackBufferHeight
                << ' ' << FormatString(params->BackBufferFormat)
                << (params->Windowed ? " windowed" : " fullscreen")
                << " depth=" << FormatString(params->AutoDepthStencilFormat);
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, D3DPRESENT_PARAMETERS*);
        return Original<Fn>(Slot_Reset)(device, params);
    }

    HRESULT WINAPI Hook_CreatePixelShader(IDirect3DDevice9* device, const DWORD* function,
                                          IDirect3DPixelShader9** shader)
    {
        uint32_t raw{};
        auto hash = RecordShader("ps", function, &raw);
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, const DWORD*, IDirect3DPixelShader9**);
        auto hr = Original<Fn>(Slot_CreatePixelShader)(device, function, shader);
        if (SUCCEEDED(hr) && shader && *shader)
        {
            std::scoped_lock lock(OutMutex());
            ShaderHashes()[*shader] = hash;
            ShaderRawHashes()[*shader] = raw;
        }
        return hr;
    }

    HRESULT WINAPI Hook_CreateVertexShader(IDirect3DDevice9* device, const DWORD* function,
                                           IDirect3DVertexShader9** shader)
    {
        uint32_t raw{};
        auto hash = RecordShader("vs", function, &raw);
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, const DWORD*, IDirect3DVertexShader9**);
        auto hr = Original<Fn>(Slot_CreateVertexShader)(device, function, shader);
        if (SUCCEEDED(hr) && shader && *shader)
        {
            std::scoped_lock lock(OutMutex());
            ShaderHashes()[*shader] = hash;
            ShaderRawHashes()[*shader] = raw;
        }
        return hr;
    }

    uint32_t HashOf(void* shader)
    {
        if (!shader)
            return 0;
        std::scoped_lock lock(OutMutex());
        auto& hashes = ShaderHashes();
        auto it = hashes.find(shader);
        return it == hashes.end() ? 0 : it->second;
    }

    uint32_t RecordFirstBind(const char* stage, void* shader)
    {
        if (!shader)
            return 0;
        std::scoped_lock lock(OutMutex());
        auto strippedIt = ShaderHashes().find(shader);
        auto rawIt = ShaderRawHashes().find(shader);
        if (strippedIt == ShaderHashes().end() || rawIt == ShaderRawHashes().end())
            return 0;

        auto stripped = strippedIt->second;
        auto raw = rawIt->second;
        auto stageBit = stage[0] == 'v' ? (uint64_t{ 1 } << 63) : 0;
        if (FirstBoundShaders().insert(stageBit | raw).second)
        {
            auto& file = FirstBindFile();
            if (file)
            {
                file << stage << ',' << std::hex << std::uppercase << std::setfill('0')
                     << std::setw(8) << raw << ',' << std::setw(8) << stripped
                     << std::dec << std::nouppercase << std::setfill(' ')
                     << ',' << gFrame.load(std::memory_order_relaxed) << '\n';
                file.flush();
            }
        }
        return stripped;
    }

    std::string Hex8(uint32_t value)
    {
        std::ostringstream out;
        out << std::hex << std::uppercase << std::setfill('0') << std::setw(8) << value;
        return out.str();
    }

    HRESULT WINAPI Hook_SetPixelShader(IDirect3DDevice9* device, IDirect3DPixelShader9* shader)
    {
        auto hash = RecordFirstBind("ps", shader);
        auto previous = gCurrentPS.exchange(hash, std::memory_order_relaxed);
        if (Cfg().traceShaderBinds && Tracing() && hash != previous)
            Write("SetPixelShader " + Hex8(hash));
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, IDirect3DPixelShader9*);
        return Original<Fn>(Slot_SetPixelShader)(device, shader);
    }

    HRESULT WINAPI Hook_SetVertexShader(IDirect3DDevice9* device, IDirect3DVertexShader9* shader)
    {
        gCurrentVS.store(RecordFirstBind("vs", shader), std::memory_order_relaxed);
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, IDirect3DVertexShader9*);
        return Original<Fn>(Slot_SetVertexShader)(device, shader);
    }

    HRESULT WINAPI Hook_CreateTexture(IDirect3DDevice9* device, UINT width, UINT height,
                                      UINT levels, DWORD usage, D3DFORMAT format, D3DPOOL pool,
                                      IDirect3DTexture9** texture, HANDLE* shared)
    {
        if (Cfg().traceResources && Tracing())
        {
            std::ostringstream out;
            out << "CreateTexture " << width << 'x' << height << " mips=" << levels
                << ' ' << FormatString(format) << " usage=0x" << std::hex << usage;
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, UINT, UINT, UINT, DWORD, D3DFORMAT,
                                    D3DPOOL, IDirect3DTexture9**, HANDLE*);
        return Original<Fn>(Slot_CreateTexture)(device, width, height, levels, usage, format,
                                                pool, texture, shared);
    }

    HRESULT WINAPI Hook_CreateRenderTarget(IDirect3DDevice9* device, UINT width, UINT height,
                                           D3DFORMAT format, D3DMULTISAMPLE_TYPE msaa,
                                           DWORD quality, BOOL lockable,
                                           IDirect3DSurface9** surface, HANDLE* shared)
    {
        if (Cfg().traceResources)
        {
            std::ostringstream out;
            out << "CreateRenderTarget " << width << 'x' << height << ' ' << FormatString(format)
                << " msaa=" << static_cast<uint32_t>(msaa);
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, UINT, UINT, D3DFORMAT, D3DMULTISAMPLE_TYPE,
                                    DWORD, BOOL, IDirect3DSurface9**, HANDLE*);
        return Original<Fn>(Slot_CreateRenderTarget)(device, width, height, format, msaa,
                                                     quality, lockable, surface, shared);
    }

    HRESULT WINAPI Hook_CreateDepthStencilSurface(IDirect3DDevice9* device, UINT width, UINT height,
                                                  D3DFORMAT format, D3DMULTISAMPLE_TYPE msaa,
                                                  DWORD quality, BOOL discard,
                                                  IDirect3DSurface9** surface, HANDLE* shared)
    {
        if (Cfg().traceResources)
        {
            std::ostringstream out;
            out << "CreateDepthStencilSurface " << width << 'x' << height
                << ' ' << FormatString(format) << " msaa=" << static_cast<uint32_t>(msaa);
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, UINT, UINT, D3DFORMAT, D3DMULTISAMPLE_TYPE,
                                    DWORD, BOOL, IDirect3DSurface9**, HANDLE*);
        return Original<Fn>(Slot_CreateDepthStencilSurface)(device, width, height, format, msaa,
                                                            quality, discard, surface, shared);
    }

    HRESULT WINAPI Hook_SetRenderTarget(IDirect3DDevice9* device, DWORD index,
                                        IDirect3DSurface9* surface)
    {
        if (Cfg().traceResources && Tracing())
        {
            std::ostringstream out;
            out << "SetRenderTarget " << index << ' ' << SurfaceDescription(surface);
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, DWORD, IDirect3DSurface9*);
        return Original<Fn>(Slot_SetRenderTarget)(device, index, surface);
    }

    HRESULT WINAPI Hook_SetDepthStencilSurface(IDirect3DDevice9* device, IDirect3DSurface9* surface)
    {
        if (Cfg().traceResources && Tracing())
            Write("SetDepthStencilSurface " + SurfaceDescription(surface));
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, IDirect3DSurface9*);
        return Original<Fn>(Slot_SetDepthStencilSurface)(device, surface);
    }

    HRESULT WINAPI Hook_SetTexture(IDirect3DDevice9* device, DWORD stage,
                                   IDirect3DBaseTexture9* texture)
    {
        if (stage < gSamplerStages.size() && texture)
            gSamplerStages[stage] = true;
        if (Cfg().traceTextures && Tracing())
        {
            std::ostringstream out;
            out << "SetTexture " << stage << ' ' << (texture ? "bound" : "null");
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, DWORD, IDirect3DBaseTexture9*);
        return Original<Fn>(Slot_SetTexture)(device, stage, texture);
    }

    HRESULT WINAPI Hook_SetPixelShaderConstantF(IDirect3DDevice9* device, UINT start,
                                                const float* data, UINT count)
    {
        for (UINT i = 0; i < count && start + i < gPixelConstants.size(); ++i)
            gPixelConstants[start + i] = true;
        if (Cfg().traceConstants && Tracing())
        {
            std::ostringstream out;
            out << "SetPixelShaderConstantF c" << start << " x" << count;
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, UINT, const float*, UINT);
        return Original<Fn>(Slot_SetPixelShaderConstantF)(device, start, data, count);
    }

    HRESULT WINAPI Hook_SetVertexShaderConstantF(IDirect3DDevice9* device, UINT start,
                                                 const float* data, UINT count)
    {
        for (UINT i = 0; i < count && start + i < gVertexConstants.size(); ++i)
            gVertexConstants[start + i] = true;
        if (Cfg().traceConstants && Tracing())
        {
            std::ostringstream out;
            out << "SetVertexShaderConstantF c" << start << " x" << count;
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, UINT, const float*, UINT);
        return Original<Fn>(Slot_SetVertexShaderConstantF)(device, start, data, count);
    }

    HRESULT WINAPI Hook_DrawPrimitive(IDirect3DDevice9* device, D3DPRIMITIVETYPE type,
                                      UINT start, UINT count)
    {
        if (Cfg().traceDraws && Tracing())
        {
            std::ostringstream out;
            out << "DrawPrimitive type=" << static_cast<uint32_t>(type) << " prims=" << count
                << " ps=" << Hex8(gCurrentPS.load(std::memory_order_relaxed))
                << " vs=" << Hex8(gCurrentVS.load(std::memory_order_relaxed));
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, D3DPRIMITIVETYPE, UINT, UINT);
        return Original<Fn>(Slot_DrawPrimitive)(device, type, start, count);
    }

    HRESULT WINAPI Hook_DrawIndexedPrimitive(IDirect3DDevice9* device, D3DPRIMITIVETYPE type,
                                             INT baseVertex, UINT minIndex, UINT numVertices,
                                             UINT startIndex, UINT primitiveCount)
    {
        if (Cfg().traceDraws && Tracing())
        {
            std::ostringstream out;
            out << "DrawIndexedPrimitive type=" << static_cast<uint32_t>(type)
                << " verts=" << numVertices << " prims=" << primitiveCount
                << " ps=" << Hex8(gCurrentPS.load(std::memory_order_relaxed))
                << " vs=" << Hex8(gCurrentVS.load(std::memory_order_relaxed));
            Write(out.str());
        }
        using Fn = HRESULT(WINAPI*)(IDirect3DDevice9*, D3DPRIMITIVETYPE, INT, UINT, UINT, UINT, UINT);
        return Original<Fn>(Slot_DrawIndexedPrimitive)(device, type, baseVertex, minIndex,
                                                       numVertices, startIndex, primitiveCount);
    }

    bool Patch(void** vtable, Slot slot, void* replacement)
    {
        DWORD oldProtect = 0;
        if (!VirtualProtect(&vtable[slot], sizeof(void*), PAGE_READWRITE, &oldProtect))
            return false;
        gOriginal[slot] = vtable[slot];
        vtable[slot] = replacement;
        VirtualProtect(&vtable[slot], sizeof(void*), oldProtect, &oldProtect);
        return true;
    }

    void Install(IDirect3DDevice9* device)
    {
        if (gInstalled.exchange(true))
            return;

        auto vtable = *reinterpret_cast<void***>(device);
        Patch(vtable, Slot_Present, &Hook_Present);
        Patch(vtable, Slot_EndScene, &Hook_EndScene);
        Patch(vtable, Slot_Reset, &Hook_Reset);
        Patch(vtable, Slot_CreateTexture, &Hook_CreateTexture);
        Patch(vtable, Slot_CreateRenderTarget, &Hook_CreateRenderTarget);
        Patch(vtable, Slot_CreateDepthStencilSurface, &Hook_CreateDepthStencilSurface);
        Patch(vtable, Slot_SetRenderTarget, &Hook_SetRenderTarget);
        Patch(vtable, Slot_SetDepthStencilSurface, &Hook_SetDepthStencilSurface);
        Patch(vtable, Slot_SetTexture, &Hook_SetTexture);
        Patch(vtable, Slot_SetPixelShader, &Hook_SetPixelShader);
        Patch(vtable, Slot_SetVertexShader, &Hook_SetVertexShader);
        Patch(vtable, Slot_SetPixelShaderConstantF, &Hook_SetPixelShaderConstantF);
        Patch(vtable, Slot_SetVertexShaderConstantF, &Hook_SetVertexShaderConstantF);
        Patch(vtable, Slot_DrawPrimitive, &Hook_DrawPrimitive);
        Patch(vtable, Slot_DrawIndexedPrimitive, &Hook_DrawIndexedPrimitive);
        Patch(vtable, Slot_CreatePixelShader, &Hook_CreatePixelShader);
        Patch(vtable, Slot_CreateVertexShader, &Hook_CreateVertexShader);

        std::ostringstream out;
        out << "d3d9 trace installed on device " << device << ", vtable " << vtable;
        ENBCompat::Log(out.str());
        Write("trace installed");
    }

    // Records which modules are in the process and in what order they sit
    // relative to the game. The proxy chain has to be known before any
    // conclusion about hook ordering means anything.
    void LogLoadedGraphicsModules()
    {
        ModuleList modules;
        modules.Enumerate(ModuleList::SearchLocation::All);

        std::ostringstream out;
        out << "graphics modules:";
        for (auto& entry : modules.m_moduleList)
        {
            auto& name = std::get<std::wstring>(entry);
            static const wchar_t* interesting[] = {
                L"d3d9", L"d3d9on12", L"enbseries", L"enbhelper", L"dxvk_d3d9",
                L"vulkan", L"vulkan-1", L"ReShade32", L"dxgi", L"icenhancer",
            };
            for (auto candidate : interesting)
            {
                if (!iequals(name, candidate))
                    continue;
                out << ' ' << std::string(name.begin(), name.end())
                    << (std::get<bool>(entry) ? "(local)" : "(system)");
                break;
            }
        }
        ENBCompat::Log(out.str());
    }

    void DumpUsageSummary()
    {
        auto listRange = [](const auto& flags, const char* label, std::ostringstream& out)
        {
            out << label;
            bool any = false;
            for (size_t i = 0; i < flags.size(); ++i)
            {
                if (!flags[i])
                    continue;
                any = true;
                auto start = i;
                while (i + 1 < flags.size() && flags[i + 1])
                    ++i;
                out << ' ' << start;
                if (i != start)
                    out << '-' << i;
            }
            if (!any)
                out << " none";
            out << '\n';
        };

        std::ostringstream out;
        out << "\n--- resource usage summary (" << gFrame.load() << " frames) ---\n";
        listRange(gPixelConstants, "pixel shader constants  c:", out);
        listRange(gVertexConstants, "vertex shader constants c:", out);
        listRange(gSamplerStages, "sampler stages           s:", out);
        Write(out.str());

        std::scoped_lock lock(OutMutex());
        if (auto& file = TraceFile())
            file.flush();
    }

    void ReadConfig()
    {
        CIniReader iniReader("");
        auto& cfg = Cfg();
        cfg.enabled = iniReader.ReadInteger("ENBCompatibility", "D3D9Trace", 0) != 0;
        cfg.dumpShaders = iniReader.ReadInteger("ENBCompatibility", "DumpShaders", 0) != 0;
        cfg.traceDraws = iniReader.ReadInteger("ENBCompatibility", "TraceDraws", 0) != 0;
        cfg.traceResources = iniReader.ReadInteger("ENBCompatibility", "TraceResources", 1) != 0;
        cfg.traceTextures = iniReader.ReadInteger("ENBCompatibility", "TraceTextures", 0) != 0;
        cfg.traceConstants = iniReader.ReadInteger("ENBCompatibility", "TraceConstants", 0) != 0;
        cfg.traceShaderBinds = iniReader.ReadInteger("ENBCompatibility", "TraceShaderBinds", 0) != 0;
        cfg.startFrame = std::max(iniReader.ReadInteger("ENBCompatibility", "TraceStartFrame", 0), 0);
        cfg.frameCount = std::max(iniReader.ReadInteger("ENBCompatibility", "TraceFrameCount", 3), 0);
        cfg.traceKey = std::clamp(iniReader.ReadInteger("ENBCompatibility", "TraceKey", 0), 0, 255);
    }
}

class ENBTraceInstaller
{
public:
    ENBTraceInstaller()
    {
        FusionFix::onInitEventAsync() += []()
        {
            ENBTrace::ReadConfig();
            if (!ENBTrace::Cfg().enabled)
                return;

            ENBTrace::LogLoadedGraphicsModules();

            // The device does not exist yet at init time and shaders start
            // being created as soon as it does, so wait for it here rather than
            // hooking from a later per-frame event and missing the shader
            // creation that matters most.
            for (int i = 0; i < 6000 && !ENBTrace::gInstalled.load(); ++i)
            {
                if (auto device = rage::grcDevice::GetD3DDevice())
                {
                    ENBTrace::Install(device);
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }

            if (!ENBTrace::gInstalled.load())
                ENBCompat::Log("d3d9 trace: device never appeared, tracing disabled");
        };

        FusionFix::onShutdownEvent() += []()
        {
            if (ENBTrace::gInstalled.load())
                ENBTrace::DumpUsageSummary();
        };
    }
} ENBTraceInstaller;
