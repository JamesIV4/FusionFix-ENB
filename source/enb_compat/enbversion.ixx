module;

#include <common.hxx>
#include <sstream>
#include <string>

export module enbversion;

import common;
import enbcompat;

// Game-version spoofing for mods that refuse to run on Complete Edition.
//
// iCEnhancer 4.0 checks the game's version and stops with "iCEnhancer requires
// GTA IV version 1.0.4.0. Please downgrade your game to the appropriate
// version." It does this by reading GTAIV.exe's *version resource* -- its import
// table names VERSION.dll's GetFileVersionInfoSizeW -- not by inspecting code or
// data inside the executable.
//
// That makes the guard satisfiable without patching anything on disk: hook the
// version-info API, let the real call run, then rewrite the VS_FIXEDFILEINFO in
// the buffer that comes back. The .asi reads what it expects and everything else
// on disk is untouched, which is the difference between a compatibility layer
// and a crack.
//
// Two deliberate limits:
//
//   * Off unless asked for. `SpoofGameVersion` is empty by default.
//   * Scoped to one module. `SpoofGameVersionFor` names the caller it applies
//     to, resolved from the hook's return address, so FusionFix's own version
//     checks and anything else in the process still see the truth.
//
// The version check exists because the mod's author did not expect it to work on
// a newer game. Satisfying it says nothing about whether the result is correct;
// it only gets us far enough to find out.

namespace ENBVersion
{
    struct Config
    {
        bool enabled = false;
        uint16_t major = 1, minor = 0, build = 4, revision = 0;
        std::wstring forModule;   // empty = every caller
        std::wstring forFile = L"gtaiv.exe";
    };

    inline Config& Cfg()
    {
        static Config cfg;
        return cfg;
    }

    inline bool ParseVersion(const std::string& text, Config& cfg)
    {
        unsigned a = 0, b = 0, c = 0, d = 0;
        auto parsed = sscanf_s(text.c_str(), "%u.%u.%u.%u", &a, &b, &c, &d);
        if (parsed < 3)
            return false;
        cfg.major = static_cast<uint16_t>(a);
        cfg.minor = static_cast<uint16_t>(b);
        cfg.build = static_cast<uint16_t>(c);
        cfg.revision = static_cast<uint16_t>(parsed >= 4 ? d : 0);
        return true;
    }

    // Which module a code address belongs to, by file name.
    inline std::wstring ModuleNameOf(void* address)
    {
        HMODULE module = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
            | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(address), &module) || !module)
            return {};
        return GetModulePath(module).filename().wstring();
    }

    inline bool CallerWanted(void* returnAddress)
    {
        auto& wanted = Cfg().forModule;
        if (wanted.empty())
            return true;

        auto caller = ModuleNameOf(returnAddress);
        if (iequals(caller, wanted))
            return true;

        // Compare without extensions too. A plugin loaded through
        // LoadPluginAfterSpoof has been renamed away from .asi to keep the ASI
        // loader off it, and requiring the config to track that rename is a
        // trap: the spoof would silently stop applying with nothing to show for
        // it but the original error message coming back.
        auto stem = [](const std::wstring& name)
        {
            return std::filesystem::path(name).stem().wstring();
        };
        return iequals(stem(caller), stem(wanted));
    }

    inline bool FileWanted(const wchar_t* path)
    {
        if (!path)
            return false;
        std::filesystem::path p(path);
        return iequals(p.filename().wstring(), Cfg().forFile);
    }

    // Rewrite the fixed-file-info block in a version-resource buffer.
    //
    // VerQueryValue finds VS_FIXEDFILEINFO by its 0xFEEF04BD signature rather
    // than at a fixed offset, so scanning for the same signature and editing in
    // place is exactly what the caller will go on to read.
    inline bool PatchBuffer(void* data, DWORD size)
    {
        if (!data || size < sizeof(VS_FIXEDFILEINFO))
            return false;

        auto bytes = static_cast<uint8_t*>(data);
        for (DWORD offset = 0; offset + sizeof(VS_FIXEDFILEINFO) <= size; offset += sizeof(DWORD))
        {
            auto info = reinterpret_cast<VS_FIXEDFILEINFO*>(bytes + offset);
            if (info->dwSignature != 0xFEEF04BDu)
                continue;

            auto& cfg = Cfg();
            auto ms = (static_cast<DWORD>(cfg.major) << 16) | cfg.minor;
            auto ls = (static_cast<DWORD>(cfg.build) << 16) | cfg.revision;
            info->dwFileVersionMS = ms;
            info->dwFileVersionLS = ls;
            info->dwProductVersionMS = ms;
            info->dwProductVersionLS = ls;
            return true;
        }
        return false;
    }

    // Function-local statics rather than namespace-scope `inline` variables:
    // in a module interface the latter produce no definition to link against.
    inline std::atomic<int>& PatchCount()
    {
        static std::atomic<int> count{ 0 };
        return count;
    }

    inline SafetyHookInline& HookW()
    {
        static SafetyHookInline hook{};
        return hook;
    }

    inline SafetyHookInline& HookExW()
    {
        static SafetyHookInline hook{};
        return hook;
    }

    inline void NotePatched(const wchar_t* path, void* returnAddress)
    {
        if (PatchCount().fetch_add(1, std::memory_order_relaxed) != 0)
            return; // log the first one only; the check usually runs once

        auto& cfg = Cfg();
        auto caller = ModuleNameOf(returnAddress);
        std::ostringstream out;
        out << "version spoof: reported " << cfg.major << '.' << cfg.minor << '.'
            << cfg.build << '.' << cfg.revision << " for "
            << std::filesystem::path(path ? path : L"?").filename().string()
            << " to " << (caller.empty() ? std::string("<unknown>")
                                         : std::string(caller.begin(), caller.end()));
        ENBCompat::Log(out.str());
    }

    inline BOOL WINAPI GetFileVersionInfoW_Hook(LPCWSTR file, DWORD handle, DWORD len, LPVOID data)
    {
        auto result = HookW().stdcall<BOOL>(file, handle, len, data);
        if (result && FileWanted(file) && CallerWanted(_ReturnAddress()))
        {
            if (PatchBuffer(data, len))
                NotePatched(file, _ReturnAddress());
        }
        return result;
    }

    inline BOOL WINAPI GetFileVersionInfoExW_Hook(DWORD flags, LPCWSTR file, DWORD handle,
                                                  DWORD len, LPVOID data)
    {
        auto result = HookExW().stdcall<BOOL>(flags, file, handle, len, data);
        if (result && FileWanted(file) && CallerWanted(_ReturnAddress()))
        {
            if (PatchBuffer(data, len))
                NotePatched(file, _ReturnAddress());
        }
        return result;
    }

    inline bool Install()
    {
        static bool installed = false;
        if (installed)
            return true;

        // version.dll forwards to the API set on modern Windows; GetProcAddress
        // resolves to whichever module actually implements it, which is the one
        // worth hooking.
        //
        // Load it rather than merely looking it up: the plugin we are doing this
        // for is what would otherwise drag version.dll in, and it has not been
        // loaded yet at this point. This runs from an init event, not from
        // DllMain, so calling LoadLibrary here is safe.
        auto module = GetModuleHandleW(L"version.dll");
        if (!module)
            module = LoadLibraryW(L"version.dll");
        if (!module)
            return false;

        if (auto target = GetProcAddress(module, "GetFileVersionInfoW"))
            HookW() = safetyhook::create_inline(target, GetFileVersionInfoW_Hook);
        if (auto target = GetProcAddress(module, "GetFileVersionInfoExW"))
            HookExW() = safetyhook::create_inline(target, GetFileVersionInfoExW_Hook);

        installed = static_cast<bool>(HookW()) || static_cast<bool>(HookExW());
        return installed;
    }

    // The FusionFix ini keeps a trailing "// ..." comment on most lines, which
    // ReadString returns verbatim. Cut at the comment and trim.
    inline std::string TrimSetting(std::string value)
    {
        auto comment = std::min(value.find("//") == std::string::npos ? value.size() : value.find("//"),
                                value.find(';') == std::string::npos ? value.size() : value.find(';'));
        value.resize(comment);
        auto first = value.find_first_not_of(" \t\r\n");
        if (first == std::string::npos)
            return {};
        return value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1);
    }

    inline std::string& RawVersionSetting()
    {
        static std::string raw;
        return raw;
    }

    inline void ReadConfig()
    {
        CIniReader iniReader("");
        auto& cfg = Cfg();

        auto version = TrimSetting(iniReader.ReadString("ENBCompatibility", "SpoofGameVersion", ""));
        RawVersionSetting() = version;
        if (version.empty() || !ParseVersion(version, cfg))
            return;

        auto target = TrimSetting(
            iniReader.ReadString("ENBCompatibility", "SpoofGameVersionFor", "icenhancer.asi"));
        cfg.forModule = std::wstring(target.begin(), target.end());

        cfg.enabled = true;
    }

    // Load a plugin ourselves, after the hook is in place.
    //
    // A plugin that checks the game version does it while loading, so the hook
    // has to exist first -- and whether it does depends on the order the ASI
    // loader happens to walk its directories, which is not something to build
    // on. Giving the file an extension the loader ignores and loading it from
    // here makes the ordering ours to decide instead of the loader's.
    inline void LoadDeferredPlugin()
    {
        CIniReader iniReader("");
        auto trimmed = TrimSetting(iniReader.ReadString("ENBCompatibility", "LoadPluginAfterSpoof", ""));
        if (trimmed.empty())
            return;

        auto path = GetExeModulePath() / std::filesystem::path(trimmed);
        std::error_code ec;
        if (!std::filesystem::exists(path, ec) || ec)
        {
            ENBCompat::Log("LoadPluginAfterSpoof: not found, " + path.string());
            return;
        }

        auto module = LoadLibraryW(path.c_str());
        ENBCompat::Log("LoadPluginAfterSpoof: " + trimmed
            + (module ? " loaded" : " FAILED to load"));
    }
}

// All of this runs from one init event, in order: read config, place the hook,
// then load the plugin.
//
// An earlier version did the first two from a static constructor, on the theory
// that a plugin checks the game version while the ASI loader is loading it and
// the hook therefore had to exist before that. Once the plugin is loaded from
// here rather than by the ASI loader, that stops being true -- the hook only has
// to precede *our* LoadLibrary, which is three lines below it. Static-init
// config reading bought nothing and could not be diagnosed from a log, because
// bailing out early is exactly the case that produces no log line.
class ENBVersionSpoof
{
public:
    ENBVersionSpoof()
    {
        FusionFix::onInitEvent() += []()
        {
            ENBVersion::ReadConfig();

            auto& cfg = ENBVersion::Cfg();
            if (!cfg.enabled)
            {
                ENBCompat::LogVerbose("version spoof: SpoofGameVersion unset or unparsable ('"
                    + ENBVersion::RawVersionSetting() + "'), not installed");
                return;
            }

            std::ostringstream out;
            out << "version spoof: reporting " << cfg.major << '.' << cfg.minor << '.'
                << cfg.build << '.' << cfg.revision << " to "
                << (cfg.forModule.empty() ? std::string("every caller")
                                          : std::string(cfg.forModule.begin(), cfg.forModule.end()));
            ENBCompat::Log(out.str());

            if (!ENBVersion::Install())
            {
                ENBCompat::Log("  FAILED: could not hook version.dll");
                return;
            }
            ENBCompat::Log("  hook placed");

            ENBVersion::LoadDeferredPlugin();
        };
    }
} ENBVersionSpoof;
