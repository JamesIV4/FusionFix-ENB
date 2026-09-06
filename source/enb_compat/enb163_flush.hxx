#pragma once

namespace ENB163
{
    using Flush = void(__thiscall*)(IDirect3DDevice9*);

    inline bool Readable(const void* address, size_t bytes)
    {
        MEMORY_BASIC_INFORMATION region{};
        return address && VirtualQuery(address, &region, sizeof(region)) && region.State == MEM_COMMIT &&
            !(region.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
            reinterpret_cast<uintptr_t>(address) + bytes >= reinterpret_cast<uintptr_t>(address) &&
            reinterpret_cast<uintptr_t>(address) + bytes <= reinterpret_cast<uintptr_t>(region.BaseAddress) + region.RegionSize;
    }
    // ENB 0.163 buffers Set*ShaderConstantF, but Get*ShaderConstantF forwards
    // straight to the underlying device. Synchronize at the draw boundary
    // before reading inputs. This is a private call, NOT a binary patch.
    // Identities recovered from the pinned decoded wrapper:
    // GetPixelShader=11E0, GetPSConstantF=28E70, queue flush=28910.
    inline Flush ResolveFlush(IDirect3DDevice9* device, std::string* diagnostic = nullptr)
    {
        auto fail = [&](std::string text) -> Flush { if (diagnostic) *diagnostic = std::move(text); return nullptr; };
        if (!Readable(device, sizeof(void*))) return fail("unreadable device");
        auto table = *reinterpret_cast<void***>(device);
        if (!Readable(table, 111 * sizeof(void*))) return fail("unreadable device table");
        HMODULE module = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(table[110]), &module)) return fail("module query error=" + std::to_string(GetLastError()));
        auto base = reinterpret_cast<unsigned char*>(module);
        if (table[110] != base + 0x28E70 || table[108] != base + 0x11E0)
            return fail("method offsets get-constants=" + std::to_string(reinterpret_cast<uintptr_t>(table[110]) - reinterpret_cast<uintptr_t>(base))
                        + " get-shader=" + std::to_string(reinterpret_cast<uintptr_t>(table[108]) - reinterpret_cast<uintptr_t>(base)));
        auto entry = base + 0x28910;
        constexpr unsigned char signature[] = {
            0x53, 0x55, 0x8b, 0xd9, 0x8b, 0x83, 0x30, 0x84,
            0x00, 0x00, 0x56, 0x57, 0x85, 0xc0, 0x0f, 0x86
        };
        if (!Readable(entry, sizeof(signature)) ||
            std::memcmp(entry, signature, sizeof(signature)) != 0) return fail("flush memory/signature differs");
        return reinterpret_cast<Flush>(entry);
    }

    inline bool FlushConstants(IDirect3DDevice9* device, std::string* diagnostic = nullptr)
    {
        auto flush = ResolveFlush(device, diagnostic);
        if (!flush) return false;
        flush(device);
        return true;
    }

    inline bool FacadeGetterPair(const void* shaderGetter, const void* constantGetter)
    {
        // Verified live GTA IV façade getters, both forwarding through +11AC.
        constexpr unsigned char shader[] = {0x8b,0x44,0x24,0x04,0x8b,0x80,0xac,0x11,0,0,0x8b,0x08,0x89,0x44,0x24,0x04,0xff,0xa1,0xb0,0x01,0,0};
        constexpr unsigned char constants[] = {0x8b,0x44,0x24,0x04,0x8b,0x80,0xac,0x11,0,0,0x8b,0x08,0x89,0x44,0x24,0x04,0xff,0xa1,0xb8,0x01,0,0};
        return Readable(shaderGetter, sizeof(shader)) && Readable(constantGetter, sizeof(constants)) &&
            std::memcmp(shaderGetter, shader, sizeof(shader)) == 0 &&
            std::memcmp(constantGetter, constants, sizeof(constants)) == 0;
    }

    inline IDirect3DDevice9* ResolveDevice(IDirect3DDevice9* gameDevice, std::string* diagnostic = nullptr)
    {
        if (ResolveFlush(gameDevice)) return gameDevice;
        auto fail = [&](const char* reason) -> IDirect3DDevice9* { if (diagnostic) *diagnostic = reason; return nullptr; };
        if (!Readable(gameDevice, sizeof(void*))) return fail("unreadable game device");
        auto table = *reinterpret_cast<void***>(gameDevice);
        if (!Readable(table, 111 * sizeof(void*))) return fail("unreadable game device table");
        HMODULE owner = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(table[110]), &owner) || owner != GetModuleHandleW(nullptr) ||
            !FacadeGetterPair(table[108], table[110])) return fail("unrecognized game device façade");
        auto field = reinterpret_cast<unsigned char*>(gameDevice) + 0x11AC;
        if (!Readable(field, sizeof(void*))) return fail("unreadable façade device link");
        IDirect3DDevice9* inner = nullptr;
        std::memcpy(&inner, field, sizeof(inner));
        if (!ResolveFlush(inner, diagnostic)) return nullptr;
        return inner;
    }
}
