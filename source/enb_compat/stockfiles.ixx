module;
#include <common.hxx>
#include <wincrypt.h>
#include <fstream>
#include "stockfiles.hxx"
#pragma comment(lib, "advapi32.lib")

export module enbstockfiles;
import common;
import enbcompat;

namespace
{
    std::string HashFile(const std::filesystem::path& path)
    {
        std::ifstream input(path, std::ios::binary | std::ios::ate);
        if (!input || input.tellg() < 0 || input.tellg() > 16 * 1024 * 1024) return {};
        std::vector<unsigned char> data(static_cast<size_t>(input.tellg()));
        input.seekg(0);
        if (!input.read(reinterpret_cast<char*>(data.data()), data.size())) return {};
        struct Crypto {
            HCRYPTPROV provider{};
            HCRYPTHASH hash{};
            ~Crypto() { if (hash) CryptDestroyHash(hash); if (provider) CryptReleaseContext(provider, 0); }
        } crypto;
        if (!CryptAcquireContextW(&crypto.provider, nullptr, nullptr, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) ||
            !CryptCreateHash(crypto.provider, CALG_SHA_256, 0, 0, &crypto.hash) ||
            !CryptHashData(crypto.hash, data.data(), static_cast<DWORD>(data.size()), 0)) return {};
        unsigned char digest[32]{};
        DWORD size = sizeof(digest);
        if (!CryptGetHashParam(crypto.hash, HP_HASHVAL, digest, &size, 0) || size != sizeof(digest)) return {};
        std::string result;
        for (auto byte : digest) { result += "0123456789abcdef"[byte >> 4]; result += "0123456789abcdef"[byte & 15]; }
        return result;
    }

    [[noreturn]] void InvalidBaseline(const wchar_t* reason)
    {
        ENBCompat::Log("stock CE shader baseline unavailable or rejected; FusionShaders fallback is forbidden");
        std::wstring message = L"FusionFix ENB mode requires the exact stock CE shader baseline.\n\n";
        message += reason;
        message += L"\n\nInstall it with tools/gamesetup/Invoke-StockENBTest.ps1 before launching."
                   L"\nThe game will close instead of loading a mixed shader pipeline.";
        FatalAppExitW(0, message.c_str());
        std::terminate();
    }
}

export namespace ENBStockFiles
{
    void Initialize()
    {
        if (!ENBCompat::Active()) return;
        using MapFile = bool(WINAPI*)(const wchar_t*, const wchar_t*, int);
        MapFile map = nullptr;
        ModuleList modules;
        modules.Enumerate(ModuleList::SearchLocation::LocalOnly);
        for (auto& entry : modules.m_moduleList)
        {
            auto module = std::get<HMODULE>(entry);
            if (IsModuleUAL(module))
            {
                map = reinterpret_cast<MapFile>(GetProcAddress(module, "AddVirtualPathForOverloadW"));
                break;
            }
        }
        if (!map) InvalidBaseline(L"The ASI loader does not expose the required file-mapping API.");
        const auto root = GetExeModulePath();
        const auto cache = root / StockCE::CacheDirectory;
        std::wstring failed;
        // Validate every byte before registering any mapping. The whitelist is
        // compiled into this ASI; a local manifest cannot bless altered shaders.
        if (!StockCE::Verify(cache, HashFile, failed)) InvalidBaseline(failed.c_str());
        for (const auto& file : StockCE::Files)
        {
            const auto physical = cache / file.path;
            for (const auto& logical : StockCE::LogicalPaths(file.path))
                if (!map(logical.c_str(), physical.c_str(), 1000000))
                    InvalidBaseline(L"A stock shader file mapping was rejected.");
        }
        // FusionFix's added shader is not a stock resource. Do not allow a
        // stale overlay to revive it if third-party content still requests it.
        for (auto variant : StockCE::Variants)
        {
            auto logical = std::wstring(L"common/shaders/") + std::wstring(variant) + L"/gta_trees_extended.fxc";
            auto missing = cache / L"disabled/gta_trees_extended.fxc";
            if (std::filesystem::exists(missing)) InvalidBaseline(L"A disabled FusionFix shader is present in the stock cache.");
            if (!map(logical.c_str(), missing.c_str(), 1000000)) InvalidBaseline(L"Extended-tree exclusion failed.");
        }
        for (auto relative : {L"db/gta_trees_extended.sps", L"dcl/gta_trees_extended.dcl"})
        {
            auto logical = std::wstring(L"common/shaders/") + relative;
            auto missing = cache / L"disabled" / relative;
            if (std::filesystem::exists(missing)) InvalidBaseline(L"A disabled FusionFix shader definition is present in the stock cache.");
            if (!map(logical.c_str(), missing.c_str(), 1000000)) InvalidBaseline(L"Extended-tree exclusion failed.");
        }
        ENBCompat::Log("exact stock CE shaders, declarations, definitions and preload list selected; normal FusionFix content remains active");
    }
}
