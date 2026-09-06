#pragma once

// Included inside ENBPostFxBridge. Diagnostics never bind shaders, change
// constants, or draw. Only a user-created request file enables GPU readback.
namespace Capture
{
    inline UINT PixelBytes(D3DFORMAT format)
    {
        switch (format)
        {
        case D3DFMT_A8R8G8B8: case D3DFMT_X8R8G8B8:
        case D3DFMT_A8B8G8R8: case D3DFMT_X8B8G8R8:
        case D3DFMT_R32F: case D3DFMT_G16R16F: return 4;
        case D3DFMT_A16B16G16R16F: case D3DFMT_G32R32F: return 8;
        case D3DFMT_A32B32G32R32F: return 16;
        case D3DFMT_R16F: return 2;
        default: return 0;
        }
    }

    struct Schedule
    {
        ULONGLONG first = 0;
        unsigned next = 0;
        bool started = false;
        int Poll(ULONGLONG now)
        {
            if (!started) { first = now; started = true; }
            constexpr ULONGLONG delays[] = {5000, 15000, 30000};
            if (next == std::size(delays) || now - first < delays[next]) return -1;
            return static_cast<int>(next++);
        }
    };

    inline std::filesystem::path directory;
    inline Schedule schedule;

    inline void Initialize()
    {
        try
        {
            std::ifstream request(GetExeModulePath() / L"plugins/ENBCompat/capture.request");
            std::string token;
            if (!(request >> token) || token != "postfx-capture-v1") return;
            SYSTEMTIME t{}; GetLocalTime(&t);
            char name[100]{};
            std::snprintf(name, sizeof(name), "postfx-%04u%02u%02u-%02u%02u%02u-%lu",
                t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond, GetCurrentProcessId());
            auto path = GetExeModulePath() / L"ENBCompat" / name;
            // Never overwrite a previous run.
            if (!std::filesystem::create_directories(path)) return;
            directory = path;
            Note(("automatic input capture armed: " + path.string()).c_str());
        }
        catch (...) { Note("capture initialization failed; rendering continues"); }
    }

    inline void Surface(IDirect3DDevice9* device, IDirect3DSurface9* source,
                        const std::filesystem::path& path, const char* label, std::ostream& report)
    {
        report << label;
        if (!source) { report << " missing\n"; return; }
        D3DSURFACE_DESC desc{};
        auto hr = source->GetDesc(&desc);
        if (FAILED(hr)) { report << " desc_hr=" << hr << '\n'; return; }
        const UINT bytes = PixelBytes(desc.Format);
        report << " width=" << desc.Width << " height=" << desc.Height
            << " format=" << desc.Format << " usage=" << desc.Usage << " pool=" << desc.Pool
            << " multisample=" << desc.MultiSampleType;
        // Readback requires a non-MSAA render target and matching system-memory
        // surface. Unsupported inputs are reported, never converted or guessed.
        if (!bytes || !desc.Width || !desc.Height || desc.Pool != D3DPOOL_DEFAULT ||
            !(desc.Usage & D3DUSAGE_RENDERTARGET) || desc.MultiSampleType != D3DMULTISAMPLE_NONE ||
            uint64_t(desc.Width) * desc.Height * bytes > 128ull * 1024 * 1024)
        { report << " skipped=unsupported_or_oversize\n"; return; }
        Ref<IDirect3DSurface9> copy;
        hr = device->CreateOffscreenPlainSurface(desc.Width, desc.Height, desc.Format,
                                                D3DPOOL_SYSTEMMEM, copy.put(), nullptr);
        if (SUCCEEDED(hr)) hr = device->GetRenderTargetData(source, copy.p);
        if (FAILED(hr)) { report << " readback_hr=" << hr << '\n'; return; }
        D3DLOCKED_RECT lock{};
        hr = copy->LockRect(&lock, nullptr, D3DLOCK_READONLY);
        if (FAILED(hr)) { report << " lock_hr=" << hr << '\n'; return; }
        struct Unlock { IDirect3DSurface9* p; ~Unlock() { p->UnlockRect(); } } unlock{copy.p};
        if (!lock.pBits || lock.Pitch < 0 || uint64_t(lock.Pitch) < uint64_t(desc.Width) * bytes)
        { report << " skipped=invalid_pitch\n"; return; }
        const UINT columns = std::min(64u, desc.Width), rows = std::min(36u, desc.Height);
        // PFX1: 8 little-endian DWORDs, then a centered uniform texel grid.
        // No float conversion, averaging, gamma correction, or tone mapping.
        const DWORD header[] = {0x31584650, desc.Width, desc.Height,
            static_cast<DWORD>(desc.Format), bytes, columns, rows, 0};
        std::ofstream output(path / (std::string(label) + ".pfx"), std::ios::binary);
        output.write(reinterpret_cast<const char*>(header), sizeof(header));
        for (UINT y = 0; y < rows; ++y)
            for (UINT x = 0; x < columns; ++x)
            {
                const auto sy = (uint64_t(2 * y + 1) * desc.Height) / (2 * rows);
                const auto sx = (uint64_t(2 * x + 1) * desc.Width) / (2 * columns);
                output.write(static_cast<const char*>(lock.pBits) + sy * lock.Pitch + sx * bytes, bytes);
            }
        report << " grid=" << columns << 'x' << rows << " saved=" << output.good() << '\n';
    }

    inline int Begin(const State& state, int slot)
    {
        if (directory.empty()) return -1;
        const int sample = schedule.Poll(GetTickCount64());
        if (sample < 0) return -1;
        try
        {
            const auto path = directory / std::to_string(sample);
            if (!std::filesystem::create_directory(path)) return -1;
            std::ofstream report(path / "inputs.txt");
            report << "boundary=backend_before_translation slot=" << slot
                << " elapsed_ms=" << GetTickCount64() - schedule.first << '\n';
            report.precision(9);
            for (UINT reg : {44u, 66u, 72u, 73u, 74u, 75u, 76u, 77u, 78u,
                            79u, 80u, 81u, 82u, 83u, 84u, 85u, 86u, 199u, 209u})
            {
                report << 'c' << reg;
                for (float value : state.constants[reg]) report << ' ' << value;
                report << '\n';
            }
            for (UINT sampler : {0u, 1u, 2u, 4u, 5u, 7u})
            {
                const auto label = "s" + std::to_string(sampler);
                report << label << " srgb=" << state.samplers[sampler][D3DSAMP_SRGBTEXTURE - 1] << '\n';
                auto texture = state.textures[sampler].p;
                Ref<IDirect3DSurface9> surface;
                if (texture && texture->GetType() == D3DRTYPE_TEXTURE)
                    static_cast<IDirect3DTexture9*>(texture)->GetSurfaceLevel(0, surface.put());
                Surface(state.device, surface.p, path, label.c_str(), report);
            }
            return sample;
        }
        catch (...) { Note("input diagnostic failed; rendering continues"); return -1; }
    }

    inline void End(const State& state, IDirect3DSurface9* depth, int sample, HRESULT drawResult)
    {
        if (sample < 0) return;
        try
        {
            const auto path = directory / std::to_string(sample);
            std::ofstream report(path / "output.txt");
            report << "boundary=backend_after_enb_draw draw_hr=" << drawResult << '\n';
            Surface(state.device, depth, path, "converted_depth", report);
            Surface(state.device, state.targets[0].p, path, "composite", report);
            Note(("automatic input/output capture complete: " + path.string()).c_str());
        }
        catch (...) { Note("output diagnostic failed; rendering continues"); }
    }
}
