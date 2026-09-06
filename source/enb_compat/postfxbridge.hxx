#pragma once
#include "enb163_flush.hxx"

// Included in postfx.ixx after its module imports. Opt-in adapter at ENB's
// device draw boundary, after GTA IV replays its queued rendering commands.
namespace ENBPostFxBridge
{
    template<class T> struct Ref
    {
        T* p = nullptr;
        Ref() = default;
        Ref(const Ref&) = delete;
        Ref& operator=(const Ref&) = delete;
        ~Ref() { reset(); }
        void reset() { if (p) { p->Release(); p = nullptr; } }
        T** put() { reset(); return &p; }
        T* operator->() const { return p; }
    };

    inline uint64_t Fingerprint(const void* data, size_t bytes)
    {
        uint64_t hash = 14695981039346656037ull;
        auto input = static_cast<const unsigned char*>(data);
        for (size_t i = 0; i < bytes; ++i)
            hash = (hash ^ input[i]) * 1099511628211ull;
        return hash;
    }

    struct ProgramID { size_t bytes = 0; uint64_t hash = 0; };

    inline ProgramID ProgramIdentity(const void* data, size_t size)
    {
        if (!data || size < 8 || size % 4) return {};
        auto input = static_cast<const unsigned char*>(data);
        auto word = [&](size_t at) { DWORD value; std::memcpy(&value, input + at, 4); return value; };
        if (word(0) != 0xFFFF0300) return {};
        std::vector<unsigned char> program(input, input + 4);
        for (size_t at = 4; at + 4 <= size;)
        {
            DWORD token = word(at);
            if (token == 0xFFFF)
            {
                if (at + 4 != size) return {};
                program.insert(program.end(), input + at, input + at + 4);
                return {program.size(), Fingerprint(program.data(), program.size())};
            }
            bool comment = (token & 0xFFFF) == 0xFFFE;
            size_t length = 4 * (1 + (comment ? ((token >> 16) & 0x7FFF) : ((token >> 24) & 0xF)));
            if (at + length > size) return {};
            if (!comment) program.insert(program.end(), input + at, input + at + length);
            at += length;
        }
        return {};
    }

    inline int ModernSlot(const void* data, size_t size)
    {
        // GetFunction can omit container comments. Match every program token,
        // not compiler/CTAB metadata that has no execution semantics.
        auto [bytes, hash] = ProgramIdentity(data, size);
        if (bytes == 2788 && hash == 0x0C5B0670CDAE0C62ull) return 13;
        if (bytes == 2788 && hash == 0x3C55DFD5663E4E28ull) return 15;
        if (bytes == 2932 && hash == 0x9839EA80B7B7E810ull) return 25;
        if (bytes == 2932 && hash == 0x46E57C6FDB49901Eull) return 27;
        if (bytes == 2492 && hash == 0x462A42518E150F1Bull) return 29;
        return -1;
    }

    inline void Note(const char* message)
    {
        static std::mutex mutex;
        std::scoped_lock lock(mutex);
        static std::set<std::string> seen;
        if (seen.insert(message).second)
            ENBCompat::Log(std::string("postfx bridge: ") + message);
    }

    constexpr D3DRENDERSTATETYPE RenderStates[] = {
        D3DRS_ZENABLE, D3DRS_ZWRITEENABLE, D3DRS_ALPHABLENDENABLE,
        D3DRS_ALPHATESTENABLE, D3DRS_SCISSORTESTENABLE, D3DRS_STENCILENABLE,
        D3DRS_FOGENABLE, D3DRS_SRGBWRITEENABLE, D3DRS_COLORWRITEENABLE,
        D3DRS_CULLMODE,
    };

    struct State
    {
        IDirect3DDevice9* device;
        Ref<IDirect3DStateBlock9> block;
        Ref<IDirect3DPixelShader9> ps;
        Ref<IDirect3DVertexShader9> vs;
        std::array<Ref<IDirect3DBaseTexture9>, 16> textures;
        std::array<Ref<IDirect3DSurface9>, 4> targets;
        Ref<IDirect3DSurface9> depth;
        D3DVIEWPORT9 viewport{};
        float constants[224][4]{};
        DWORD samplers[8][13]{};
        DWORD render[std::size(RenderStates)]{};
        bool armed = false;

        explicit State(IDirect3DDevice9* d) : device(d) {}
        ~State() { if (armed) Restore(); }

        bool Capture()
        {
            if (FAILED(device->CreateStateBlock(D3DSBT_ALL, block.put())) ||
                FAILED(device->GetPixelShader(ps.put())) || FAILED(device->GetVertexShader(vs.put())) ||
                FAILED(device->GetViewport(&viewport)) ||
                FAILED(device->GetPixelShaderConstantF(0, &constants[0][0], 224))) return false;
            auto hr = device->GetDepthStencilSurface(depth.put());
            if (FAILED(hr) && hr != D3DERR_NOTFOUND) return false;
            for (UINT i = 0; i < targets.size(); ++i)
            {
                hr = device->GetRenderTarget(i, targets[i].put());
                if (FAILED(hr) && (i == 0 || hr != D3DERR_NOTFOUND)) return false;
            }
            for (UINT i = 0; i < textures.size(); ++i)
                if (FAILED(device->GetTexture(i, textures[i].put()))) return false;
            for (UINT i = 0; i < 8; ++i)
                for (UINT s = 1; s <= 13; ++s)
                    if (FAILED(device->GetSamplerState(i, static_cast<D3DSAMPLERSTATETYPE>(s), &samplers[i][s - 1]))) return false;
            for (size_t i = 0; i < std::size(RenderStates); ++i)
                if (FAILED(device->GetRenderState(RenderStates[i], &render[i]))) return false;
            armed = true;
            return true;
        }

        bool Restore()
        {
            if (!armed) return true;
            armed = false;
            bool okay = true;
            auto check = [&](HRESULT hr) { okay = SUCCEEDED(hr) && okay; };
            // Unbind our output before restoring render targets. RT/DS are
            // restored explicitly; do not rely on the state block for them.
            check(device->SetTexture(1, nullptr));
            check(device->SetDepthStencilSurface(nullptr));
            for (UINT i = 1; i < targets.size(); ++i) check(device->SetRenderTarget(i, nullptr));
            for (UINT i = 0; i < targets.size(); ++i) check(device->SetRenderTarget(i, targets[i].p));
            check(device->SetDepthStencilSurface(depth.p));
            check(block->Apply());
            // Replay through the wrapper too: an opaque state block can bypass
            // ENB's cached shader/texture/constant bindings.
            check(device->SetVertexShader(vs.p));
            check(device->SetPixelShader(ps.p));
            // Only these registers were written through the outer wrapper by
            // the bridge. Other hardware constants are restored by the block;
            // do not submit a spurious game upload of all 224 registers.
            check(device->SetPixelShaderConstantF(0, &constants[0][0], 2));
            check(device->SetPixelShaderConstantF(85, constants[85], 1));
            for (UINT i = 0; i < textures.size(); ++i) check(device->SetTexture(i, textures[i].p));
            for (UINT i = 0; i < 8; ++i)
                for (UINT s = 1; s <= 13; ++s)
                    check(device->SetSamplerState(i, static_cast<D3DSAMPLERSTATETYPE>(s), samplers[i][s - 1]));
            for (size_t i = 0; i < std::size(RenderStates); ++i)
                check(device->SetRenderState(RenderStates[i], render[i]));
            check(device->SetViewport(&viewport));
            if (!okay) Note("state restore failed; skip fallback draw and wait for device recovery");
            return okay;
        }
    };

    inline Ref<IDirect3DPixelShader9> legacyShader, conversionShader;
    inline Ref<IDirect3DTexture9> convertedDepth;
    inline Ref<IDirect3DSurface9> convertedSurface;
    inline UINT width = 0, height = 0;
    inline bool assetsFailed = false;

    inline void __fastcall Lost()
    {
        convertedSurface.reset(); convertedDepth.reset();
        legacyShader.reset(); conversionShader.reset();
        width = height = 0;
        assetsFailed = false;
    }
    inline void __fastcall Reset() {} // Recreate lazily on the next eligible draw.

    inline bool LoadShader(IDirect3DDevice9* device, const wchar_t* name, size_t bytes,
                           uint64_t expected, Ref<IDirect3DPixelShader9>& shader)
    {
        auto path = GetExeModulePath() / L"plugins" / L"ENBCompat" / name;
        std::ifstream stream(path, std::ios::binary | std::ios::ate);
        if (!stream || stream.tellg() != static_cast<std::streamoff>(bytes)) return false;
        std::vector<DWORD> code(bytes / 4);
        stream.seekg(0);
        stream.read(reinterpret_cast<char*>(code.data()), bytes);
        return stream.good() && Fingerprint(code.data(), bytes) == expected &&
            SUCCEEDED(device->CreatePixelShader(code.data(), shader.put()));
    }

    inline bool Resources(IDirect3DDevice9* device, UINT w, UINT h)
    {
        if (assetsFailed) return false;
        if (!legacyShader.p || !conversionShader.p)
        {
            if (!LoadShader(device, L"legacy_composite.cso", 3800, 0x05080A0DC2BF80B3ull, legacyShader) ||
                !LoadShader(device, L"legacy_depth.cso", 456, 0x81BC637FB46B15D2ull, conversionShader))
            {
                assetsFailed = true;
                Note("missing, changed or rejected shader assets; original draw retained");
                return false;
            }
        }
        if (width != w || height != h || !convertedSurface.p)
        {
            convertedSurface.reset(); convertedDepth.reset();
            width = height = 0;
            if (FAILED(device->CreateTexture(w, h, 1, D3DUSAGE_RENDERTARGET, D3DFMT_R32F,
                                            D3DPOOL_DEFAULT, convertedDepth.put(), nullptr)) ||
                FAILED(convertedDepth->GetSurfaceLevel(0, convertedSurface.put()))) return false;
            width = w; height = h;
        }
        return true;
    }

    #include "postfxcapture.hxx"

    // true means a final draw was attempted, or restoring state failed (so a
    // second draw would be unsafe). false permits the original game draw.
    inline bool Draw(IDirect3DDevice9* device, D3DPRIMITIVETYPE type, UINT start,
                     UINT count, HRESULT& outcome)
    {
        outcome = E_FAIL;
        if (!device) return false;
        Ref<IDirect3DPixelShader9> shader;
        UINT bytes = 0;
        if (FAILED(device->GetPixelShader(shader.put())) || !shader.p ||
            FAILED(shader->GetFunction(nullptr, &bytes)) || bytes == 0 || bytes > 65536 || bytes % 4) return false;
        std::vector<DWORD> code(bytes / 4);
        if (FAILED(shader->GetFunction(code.data(), &bytes))) return false;
        int slot = ModernSlot(code.data(), bytes);
        if (slot < 0) return false;
        Note(("recognized modern composite slot " + std::to_string(slot)).c_str());
        std::string flushDiagnostic;
        if (!ENB163::FlushConstants(device, &flushDiagnostic))
        {
            Note(("ENB queue-flush check failed: " + flushDiagnostic + "; original draw retained").c_str());
            return false;
        }
        State state(device);
        if (!state.Capture()) { Note("input capture failed; original draw retained"); return false; }
        auto& clip = state.constants[77];
        auto& log = state.constants[209];
        // Fail closed if the expected provider/viewport contract is absent.
        if (!(std::isfinite(clip[0]) && std::isfinite(clip[1]) && std::isfinite(log[2]) && std::isfinite(log[3]) &&
              clip[0] > 0 && clip[1] > clip[0] && log[3] > 0 && log[2] > 1 &&
              std::abs(log[3] / clip[0] - 1) < 0.01f &&
              std::abs(log[2] * log[3] / clip[1] - 1) < 0.01f))
        {
            Note("clip/log-depth constants disagree; original draw retained");
            return !state.Restore();
        }
        for (UINT i = 0; i < 8; ++i)
            if (!state.textures[i].p && i != 3) { Note("required composite texture missing"); return !state.Restore(); }
        if (state.textures[1]->GetType() != D3DRTYPE_TEXTURE) return !state.Restore();
        D3DSURFACE_DESC desc{};
        if (FAILED(static_cast<IDirect3DTexture9*>(state.textures[1].p)->GetLevelDesc(0, &desc)) ||
            state.viewport.X || state.viewport.Y || state.viewport.Width != desc.Width ||
            state.viewport.Height != desc.Height || !Resources(device, desc.Width, desc.Height))
        {
            Note("depth dimensions/resource preparation failed; original draw retained");
            return !state.Restore();
        }
        const int diagnostic = Capture::Begin(state, slot);
        bool okay = true;
        auto check = [&](HRESULT hr) { okay = SUCCEEDED(hr) && okay; };
        check(device->SetDepthStencilSurface(nullptr));
        for (UINT i = 1; i < 4; ++i) check(device->SetRenderTarget(i, nullptr));
        check(device->SetRenderTarget(0, convertedSurface.p));
        check(device->SetViewport(&state.viewport));
        for (auto r : { D3DRS_ZENABLE, D3DRS_ZWRITEENABLE, D3DRS_ALPHABLENDENABLE, D3DRS_ALPHATESTENABLE,
                        D3DRS_SCISSORTESTENABLE, D3DRS_STENCILENABLE, D3DRS_FOGENABLE, D3DRS_SRGBWRITEENABLE })
            check(device->SetRenderState(r, FALSE));
        check(device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE));
        check(device->SetRenderState(D3DRS_COLORWRITEENABLE, 15));
        check(device->SetPixelShader(conversionShader.p));
        check(device->SetTexture(1, state.textures[1].p));
        check(device->SetPixelShaderConstantF(0, clip, 1));
        check(device->SetPixelShaderConstantF(1, log, 1));
        check(device->SetSamplerState(1, D3DSAMP_MINFILTER, D3DTEXF_POINT));
        check(device->SetSamplerState(1, D3DSAMP_MAGFILTER, D3DTEXF_POINT));
        check(device->SetSamplerState(1, D3DSAMP_MIPFILTER, D3DTEXF_NONE));
        check(device->SetSamplerState(1, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP));
        check(device->SetSamplerState(1, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP));
        check(device->SetSamplerState(1, D3DSAMP_SRGBTEXTURE, FALSE));
        if (okay) okay = SUCCEEDED(device->DrawPrimitive(type, start, count));
        if (!state.Restore()) return true;
        if (!okay) { Note("depth conversion failed; original draw retained"); return false; }
        // Re-arm the original snapshot for the final pass's restoration. Its
        // saved inputs remain alive until relocation and drawing finish.
        state.armed = true;
        check(device->SetTexture(1, convertedDepth.p));
        for (UINT destination = 3; destination <= 6; ++destination)
        {
            const UINT source = destination + 1;
            check(device->SetTexture(destination, state.textures[source].p));
            for (UINT s = 1; s <= 13; ++s)
                check(device->SetSamplerState(destination, static_cast<D3DSAMPLERSTATETYPE>(s), state.samplers[source][s - 1]));
        }
        check(device->SetPixelShaderConstantF(85, state.constants[86], 1));
        check(device->SetPixelShader(legacyShader.p));
        if (!okay) { Note("input relocation failed; original draw retained"); return !state.Restore(); }
        auto hr = device->DrawPrimitive(type, start, count);
        Capture::End(state, convertedSurface.p, diagnostic, hr);
        outcome = state.Restore() ? hr : E_FAIL;
        if (FAILED(hr)) Note("ENB composite draw returned failure");
        else Note("legacy composite draw submitted with converted depth and relocated inputs");
        return true;
    }

    using DrawFn = HRESULT(WINAPI*)(IDirect3DDevice9*, D3DPRIMITIVETYPE, UINT, UINT);
    inline std::atomic<DrawFn> originalDraw{nullptr};
    inline thread_local bool insideBridge = false;

    template<class Adapter>
    HRESULT Dispatch(DrawFn original, Adapter&& adapter, bool& inside, IDirect3DDevice9* device,
                     D3DPRIMITIVETYPE type, UINT start, UINT count)
    {
        if (!original) return E_FAIL;
        if (inside) return original(device, type, start, count);
        struct Guard { bool& flag; ~Guard() { flag = false; } } guard{inside};
        inside = true;
        HRESULT outcome = E_FAIL;
        try
        {
            if (adapter(device, type, start, count, outcome)) return outcome;
            return original(device, type, start, count);
        }
        catch (...)
        {
            Note("adapter exception; draw not repeated");
            return E_FAIL;
        }
    }

    inline HRESULT WINAPI HookDraw(IDirect3DDevice9* device, D3DPRIMITIVETYPE type, UINT start, UINT count)
    {
        return Dispatch(originalDraw.load(std::memory_order_acquire), Draw, insideBridge, device, type, start, count);
    }

    inline bool Install(IDirect3DDevice9* gameDevice)
    {
        // Called from the game-side hook only to find/install the backend.
        // Rendering work happens in HookDraw on command replay, not here.
        static std::mutex mutex;
        static void** installedTable = nullptr;
        std::scoped_lock lock(mutex);
        std::string reason;
        auto device = ENB163::ResolveDevice(gameDevice, &reason);
        if (!device) { Note(("backend resolution failed: " + reason).c_str()); return false; }
        auto table = *reinterpret_cast<void***>(device);
        if (table == installedTable) return true;
        if (installedTable) { Note("different backend table encountered; not rebound"); return false; }
        DWORD protection = 0;
        if (!VirtualProtect(table + 81, sizeof(void*), PAGE_READWRITE, &protection))
        { Note("backend vtable protection failed"); return false; }
        originalDraw.store(reinterpret_cast<DrawFn>(table[81]), std::memory_order_release);
        InterlockedExchangePointer(reinterpret_cast<void* volatile*>(table + 81), reinterpret_cast<void*>(&HookDraw));
        DWORD ignored = 0;
        VirtualProtect(table + 81, sizeof(void*), protection, &ignored);
        installedTable = table;
        Capture::Initialize();
        auto lost = rage::grcDevice::Functor0(NULL, Lost, NULL, 0);
        auto reset = rage::grcDevice::Functor0(NULL, Reset, NULL, 0);
        rage::grcDevice::RegisterDeviceCallbacks(lost, reset);
        Note("ENB draw boundary installed after game command queue");
        return true;
    }
}
