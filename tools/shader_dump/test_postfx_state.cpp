// Headless test of the production state guard, using a COM-shaped fake device.
// No D3D DLL is loaded and no graphics device is created.
#define NOMINMAX
#include <windows.h>
#include <d3d9.h>
#include <array>
#include <vector>
#include <set>
#include <string>
#include <string_view>
#include <filesystem>
#include <fstream>
#include <cmath>
#include <cassert>
#include <cstring>
#include <iostream>
#include <mutex>
#include <atomic>
#include <algorithm>
#include <cstdio>
#include <sstream>

namespace ENBCompat { inline void Log(std::string_view) {} }
inline std::filesystem::path GetExeModulePath() { return {}; }
namespace rage::grcDevice {
    struct Functor0 { Functor0(void*, void(__fastcall*)(), void*, int) {} };
    inline void RegisterDeviceCallbacks(Functor0, Functor0) {}
}
#include "../../source/enb_compat/postfxbridge.hxx"

struct Object { void** table; long refs = 0; };
struct Values {
    void* ps{}; void* vs{}; void* depth{};
    std::array<void*, 16> textures{};
    std::array<void*, 4> targets{};
    std::array<float, 224 * 4> constants{};
    std::array<std::array<DWORD, 13>, 8> samplers{};
    std::array<DWORD, 256> render{};
    D3DVIEWPORT9 viewport{};
};
struct Device {
    void** table;
    Values hardware, cache, saved;
    Object block;
    int failGetTexture = -1;
    bool failSetTexture = false;
};
static Device* active;
static int drawCalls = 0;
static HRESULT WINAPI OriginalDraw(IDirect3DDevice9*, D3DPRIMITIVETYPE type, UINT start, UINT count) {
    assert(type == D3DPT_TRIANGLESTRIP && start == 7 && count == 2);
    ++drawCalls;
    return S_FALSE;
}
static ULONG WINAPI AddRef(Object* o) { return ++o->refs; }
static ULONG WINAPI Release(Object* o) { assert(o->refs > 0); return --o->refs; }
struct CaptureSurface {
    void** table; long refs = 0;
    D3DSURFACE_DESC desc{};
    float pixels[6] = {0.25f, 2.0f, -999.0f, 4.0f, 8.0f, -999.0f};
    bool locked = false;
};
static CaptureSurface* captureCopy;
static bool failReadback = false;
static int readbackCalls = 0;
static HRESULT WINAPI CaptureDesc(CaptureSurface* surface, D3DSURFACE_DESC* desc) {
    *desc = surface->desc; return S_OK;
}
static HRESULT WINAPI CaptureLock(CaptureSurface* surface, D3DLOCKED_RECT* lock, const RECT*, DWORD flags) {
    assert(flags == D3DLOCK_READONLY && !surface->locked);
    surface->locked = true; lock->Pitch = 12; lock->pBits = surface->pixels; return S_OK;
}
static HRESULT WINAPI CaptureUnlock(CaptureSurface* surface) {
    assert(surface->locked); surface->locked = false; return S_OK;
}
static HRESULT WINAPI CaptureCreate(void*, UINT w, UINT h, D3DFORMAT format, D3DPOOL pool,
                                   IDirect3DSurface9** out, HANDLE*) {
    assert(w == 2 && h == 2 && format == D3DFMT_R32F && pool == D3DPOOL_SYSTEMMEM);
    ++captureCopy->refs; *out = reinterpret_cast<IDirect3DSurface9*>(captureCopy); return S_OK;
}
static HRESULT WINAPI CaptureRead(void*, IDirect3DSurface9*, IDirect3DSurface9*) {
    ++readbackCalls; return failReadback ? E_FAIL : S_OK;
}
static void TestReadback() {
    std::array<void*, 119> deviceTable{};
    std::array<void*, 17> surfaceTable{};
    deviceTable[32] = reinterpret_cast<void*>(&CaptureRead);
    deviceTable[36] = reinterpret_cast<void*>(&CaptureCreate);
    surfaceTable[2] = reinterpret_cast<void*>(&Release);
    surfaceTable[12] = reinterpret_cast<void*>(&CaptureDesc);
    surfaceTable[13] = reinterpret_cast<void*>(&CaptureLock);
    surfaceTable[14] = reinterpret_cast<void*>(&CaptureUnlock);
    Object device{deviceTable.data()};
    CaptureSurface source{surfaceTable.data()}, copy{surfaceTable.data()};
    captureCopy = &copy;
    source.desc = {D3DFMT_R32F, D3DRTYPE_SURFACE, D3DUSAGE_RENDERTARGET,
        D3DPOOL_DEFAULT, D3DMULTISAMPLE_NONE, 0, 2, 2};
    auto path = std::filesystem::path("build") / ("capture-headless-" + std::to_string(GetCurrentProcessId()));
    assert(std::filesystem::create_directory(path));
    std::ostringstream report;
    auto run = [&] { ENBPostFxBridge::Capture::Surface(reinterpret_cast<IDirect3DDevice9*>(&device),
        reinterpret_cast<IDirect3DSurface9*>(&source), path, "test", report); };
    run();
    assert(copy.refs == 0 && !copy.locked && readbackCalls == 1);
    std::ifstream file(path / "test.pfx", std::ios::binary);
    DWORD header[8]{}; float samples[4]{};
    file.read(reinterpret_cast<char*>(header), sizeof(header));
    file.read(reinterpret_cast<char*>(samples), sizeof(samples));
    assert(file.good() && header[0] == 0x31584650 && header[5] == 2 && header[6] == 2);
    assert(samples[0] == .25f && samples[1] == 2 && samples[2] == 4 && samples[3] == 8);
    file.close();
    failReadback = true; run();
    assert(copy.refs == 0 && !copy.locked && readbackCalls == 2);
    source.desc.MultiSampleType = D3DMULTISAMPLE_2_SAMPLES; run();
    assert(readbackCalls == 2);
    std::filesystem::remove(path / "test.pfx");
    std::filesystem::remove(path);
    std::cout << "Readback diagnostics: padded pitch, raw HDR values, failed copy cleanup and MSAA rejection passed.\n";
}
static HRESULT Give(void* object, void** out) {
    *out = object;
    if (object) AddRef(static_cast<Object*>(object));
    return S_OK;
}
static HRESULT WINAPI Apply(Object*) {
    // Model an opaque state block: restore hardware but bypass wrapper caches;
    // render targets/depth surface are deliberately NOT part of this block.
    auto targets = active->hardware.targets;
    auto depth = active->hardware.depth;
    active->hardware = active->saved;
    active->hardware.targets = targets;
    active->hardware.depth = depth;
    return S_OK;
}
static HRESULT WINAPI CreateBlock(Device* d, D3DSTATEBLOCKTYPE, void** out) {
    d->saved = d->hardware;
    return Give(&d->block, out);
}
static HRESULT WINAPI GetPS(Device* d, void** p) { return Give(d->cache.ps, p); }
static HRESULT WINAPI GetVS(Device* d, void** p) { return Give(d->cache.vs, p); }
static HRESULT WINAPI GetDepth(Device* d, void** p) { return Give(d->cache.depth, p); }
static HRESULT WINAPI GetRT(Device* d, DWORD i, void** p) { return Give(d->cache.targets.at(i), p); }
static HRESULT WINAPI GetTexture(Device* d, DWORD i, void** p) {
    if (static_cast<int>(i) == d->failGetTexture) { *p = nullptr; return E_FAIL; }
    return Give(d->cache.textures.at(i), p);
}
static HRESULT WINAPI GetViewport(Device* d, D3DVIEWPORT9* p) { *p = d->cache.viewport; return S_OK; }
static HRESULT WINAPI GetConstants(Device* d, UINT start, float* p, UINT n) {
    std::memcpy(p, d->cache.constants.data() + start * 4, n * 16); return S_OK;
}
static HRESULT WINAPI GetSampler(Device* d, DWORD i, D3DSAMPLERSTATETYPE s, DWORD* p) {
    *p = d->cache.samplers.at(i).at(s - 1); return S_OK;
}
static HRESULT WINAPI GetRender(Device* d, D3DRENDERSTATETYPE s, DWORD* p) {
    *p = d->cache.render.at(s); return S_OK;
}
static HRESULT WINAPI SetPS(Device* d, void* p) { d->cache.ps = d->hardware.ps = p; return S_OK; }
static HRESULT WINAPI SetVS(Device* d, void* p) { d->cache.vs = d->hardware.vs = p; return S_OK; }
static HRESULT WINAPI SetDepth(Device* d, void* p) { d->cache.depth = d->hardware.depth = p; return S_OK; }
static HRESULT WINAPI SetRT(Device* d, DWORD i, void* p) {
    d->cache.targets.at(i) = d->hardware.targets.at(i) = p;
    d->cache.viewport.Width = d->hardware.viewport.Width = 999; // D3D changes viewport on RT bind.
    return S_OK;
}
static HRESULT WINAPI SetTexture(Device* d, DWORD i, void* p) {
    if (d->failSetTexture) { d->failSetTexture = false; return E_FAIL; }
    d->cache.textures.at(i) = d->hardware.textures.at(i) = p; return S_OK;
}
static HRESULT WINAPI SetViewport(Device* d, const D3DVIEWPORT9* p) { d->cache.viewport = d->hardware.viewport = *p; return S_OK; }
static HRESULT WINAPI SetConstants(Device* d, UINT start, const float* p, UINT n) {
    std::memcpy(d->cache.constants.data() + start * 4, p, n * 16);
    std::memcpy(d->hardware.constants.data() + start * 4, p, n * 16); return S_OK;
}
static HRESULT WINAPI SetSampler(Device* d, DWORD i, D3DSAMPLERSTATETYPE s, DWORD p) {
    d->cache.samplers.at(i).at(s - 1) = d->hardware.samplers.at(i).at(s - 1) = p; return S_OK;
}
static HRESULT WINAPI SetRender(Device* d, D3DRENDERSTATETYPE s, DWORD p) {
    d->cache.render.at(s) = d->hardware.render.at(s) = p; return S_OK;
}
static void Equal(const Values& a, const Values& b) {
    assert(a.ps == b.ps && a.vs == b.vs && a.depth == b.depth);
    assert(a.textures == b.textures && a.targets == b.targets && a.constants == b.constants);
    assert(a.samplers == b.samplers);
    for (auto s : ENBPostFxBridge::RenderStates) assert(a.render[s] == b.render[s]);
    assert(std::memcmp(&a.viewport, &b.viewport, sizeof(a.viewport)) == 0);
}
int main(int argc, char** argv) {
    void* objectTable[6]{};
    objectTable[1] = reinterpret_cast<void*>(&AddRef); objectTable[2] = reinterpret_cast<void*>(&Release);
    objectTable[5] = reinterpret_cast<void*>(&Apply);
    void* table[119]{};
#define SLOT(n, name) table[n] = reinterpret_cast<void*>(&name)
    SLOT(59, CreateBlock); SLOT(108, GetPS); SLOT(93, GetVS); SLOT(40, GetDepth); SLOT(38, GetRT);
    SLOT(64, GetTexture); SLOT(48, GetViewport); SLOT(110, GetConstants); SLOT(68, GetSampler); SLOT(58, GetRender);
    SLOT(107, SetPS); SLOT(92, SetVS); SLOT(39, SetDepth); SLOT(37, SetRT); SLOT(65, SetTexture);
    SLOT(47, SetViewport); SLOT(109, SetConstants); SLOT(69, SetSampler); SLOT(57, SetRender);
#undef SLOT
    Object objects[23]{};
    for (auto& o : objects) o.table = objectTable;
    Device d{}; d.table = table; d.block.table = objectTable; active = &d;
    d.cache.ps = &objects[0]; d.cache.vs = &objects[1]; d.cache.depth = &objects[2];
    for (int i = 0; i < 16; ++i) d.cache.textures[i] = &objects[3 + i];
    for (int i = 0; i < 4; ++i) d.cache.targets[i] = &objects[19 + i];
    for (size_t i = 0; i < d.cache.constants.size(); ++i) d.cache.constants[i] = static_cast<float>(i);
    for (int i = 0; i < 8; ++i) for (int s = 0; s < 13; ++s) d.cache.samplers[i][s] = i * 100 + s;
    for (auto s : ENBPostFxBridge::RenderStates) d.cache.render[s] = s + 10;
    d.cache.viewport = {0, 0, 1280, 720, 0, 1}; d.hardware = d.cache;
    const auto original = d.cache;
    auto device = reinterpret_cast<IDirect3DDevice9*>(&d);
    for (bool fail : {false, true}) {
        {
            ENBPostFxBridge::State state(device);
            assert(state.Capture());
            // Overlapping sampler relocation, constants and output state all change.
            d.cache = {}; d.hardware = {};
            // Only c0/c1/c85 were submitted by the bridge through the wrapper.
            // Other cache entries keep their original values; ENB may change
            // the corresponding hardware values privately during its draws.
            d.cache.constants = original.constants;
            for (int i : {0, 1, 85}) for (int c = 0; c < 4; ++c) d.cache.constants[i * 4 + c] = -123;
            d.failSetTexture = fail;
            assert(state.Restore() == !fail);
            Equal(d.cache, original); Equal(d.hardware, original);
        }
        for (const auto& o : objects) assert(o.refs == 0);
        assert(d.block.refs == 0);
    }
    d.failGetTexture = 5;
    { ENBPostFxBridge::State state(device); assert(!state.Capture()); }
    for (const auto& o : objects) assert(o.refs == 0);
    assert(d.block.refs == 0);
    Equal(d.cache, original); Equal(d.hardware, original);
    std::cout << "Production state guard: wrapper-cache restoration, failed restore, partial capture and COM reference balance passed.\n";
    {
        bool inside = false;
        auto pass = [](auto*, auto, auto, auto, HRESULT&) { return false; };
        auto handled = [](auto*, auto, auto, auto, HRESULT& result) { result = S_OK; return true; };
        auto invoke = [&](auto adapter) { return ENBPostFxBridge::Dispatch(OriginalDraw, adapter, inside, device, D3DPT_TRIANGLESTRIP, 7, 2); };
        drawCalls = 0;
        assert(invoke(pass) == S_FALSE && drawCalls == 1 && !inside);
        drawCalls = 0;
        assert(invoke(handled) == S_OK && drawCalls == 0 && !inside);
        auto nested = [&](auto* d, auto type, auto start, auto count, HRESULT& result) {
            auto forbidden = [](auto*, auto, auto, auto, HRESULT&) { assert(false); return true; };
            result = ENBPostFxBridge::Dispatch(OriginalDraw, forbidden, inside, d, type, start, count);
            return true;
        };
        assert(invoke(nested) == S_FALSE && drawCalls == 1 && !inside);
        drawCalls = 0;
        auto failure = [](auto*, auto, auto, auto, HRESULT&) -> bool { throw 1; };
        assert(invoke(failure) == E_FAIL && drawCalls == 0 && !inside);
        std::cout << "Production draw dispatcher: original arguments/results, handled draw, recursion and exception cleanup passed.\n";
    }
    {
        // Getter prefixes captured from GTAIV.exe in the live device-chain report.
        unsigned char ps[] = {0x8b,0x44,0x24,0x04,0x8b,0x80,0xac,0x11,0,0,0x8b,0x08,0x89,0x44,0x24,0x04,0xff,0xa1,0xb0,0x01,0,0};
        unsigned char constants[] = {0x8b,0x44,0x24,0x04,0x8b,0x80,0xac,0x11,0,0,0x8b,0x08,0x89,0x44,0x24,0x04,0xff,0xa1,0xb8,0x01,0,0};
        assert(ENB163::FacadeGetterPair(ps, constants));
        constants[6] ^= 4;
        assert(!ENB163::FacadeGetterPair(ps, constants));
        assert(!ENB163::FacadeGetterPair(nullptr, constants));
        assert(ENB163::ResolveDevice(nullptr) == nullptr);
        std::cout << "Captured game facade getter pair accepted; altered link and null inputs rejected.\n";
    }
    if (argc >= 2) {
        TestReadback();
        ENBPostFxBridge::Capture::Schedule schedule;
        assert(schedule.Poll(0) == -1);
        assert(schedule.Poll(4999) == -1);
        assert(schedule.Poll(5000) == 0);
        assert(schedule.Poll(5000) == -1);
        assert(schedule.Poll(15000) == 1);
        assert(schedule.Poll(30000) == 2);
        assert(schedule.Poll(90000) == -1);
        assert(ENBPostFxBridge::Capture::PixelBytes(D3DFMT_A16B16G16R16F) == 8);
        assert(ENBPostFxBridge::Capture::PixelBytes(D3DFMT_D24S8) == 0);
        std::cout << "Diagnostic capture schedule is delayed and bounded; unsupported formats rejected.\n";
        for (int slot : {13, 15, 25, 27, 29}) {
            auto path = std::filesystem::path(argv[1]) / ("modern" + std::to_string(slot) + ".cso");
            std::ifstream file(path, std::ios::binary);
            std::vector<char> code((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            assert(!code.empty());
            assert(ENBPostFxBridge::ModernSlot(code.data(), code.size()) == slot);
            // Extra metadata must not alter the executable-program identity.
            const char comment[] = {-2, -1, 1, 0, 't', 'e', 's', 't'};
            code.insert(code.end() - 4, std::begin(comment), std::end(comment));
            assert(ENBPostFxBridge::ModernSlot(code.data(), code.size()) == slot);
            code.back() ^= 1;
            assert(ENBPostFxBridge::ModernSlot(code.data(), code.size()) == -1);
        }
        std::cout << "Production shader router: five real modern programs accepted; five mutated programs rejected.\n";
    }
    if (argc >= 3) {
        std::ifstream file(argv[2], std::ios::binary);
        std::vector<char> code((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        assert(ENBPostFxBridge::ModernSlot(code.data(), code.size()) == 13);
        std::cout << "Captured in-game comment-stripped composite recognized as slot 13.\n";
    }
}
