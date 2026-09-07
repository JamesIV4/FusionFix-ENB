#pragma once
#include <array>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace StockCE
{
    struct File { std::wstring_view path; std::string_view sha256; };
    inline constexpr File Files[] = {
        #include "stockfiles.inc"
    };
    inline constexpr std::wstring_view Variants[] = {
        L"win32_30", L"win32_30_low_ati", L"win32_30_nv6",
        L"win32_30_nv7", L"win32_30_nv8", L"win32_30_atidx10"
    };
    inline constexpr auto CacheDirectory = L"plugins/ENBCompat/StockCE";

    inline std::vector<std::wstring> LogicalPaths(std::wstring_view relative)
    {
        std::vector<std::wstring> result;
        constexpr std::wstring_view variant = L"win32_30_nv8/";
        if (relative.starts_with(variant))
        {
            for (auto folder : Variants)
                result.emplace_back(std::wstring(L"common/shaders/") + std::wstring(folder)
                                    + L"/" + std::wstring(relative.substr(variant.size())));
        }
        else result.emplace_back(std::wstring(L"common/shaders/") + std::wstring(relative));
        return result;
    }

    template<class HashFile>
    bool Verify(const std::filesystem::path& cache, HashFile hash, std::wstring& failed)
    {
        for (const auto& file : Files)
        {
            if (hash(cache / file.path) != file.sha256)
            {
                failed = file.path;
                return false;
            }
        }
        return true;
    }
}
