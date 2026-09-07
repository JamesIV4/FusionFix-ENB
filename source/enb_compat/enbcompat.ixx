module;

#include <common.hxx>
#include <fstream>
#include <sstream>
#include <filesystem>

export module enbcompat;

import common;
import settings;

// ENB mode is a fixed stock-CE shader contract. Every FusionFix shader feature
// and dependent GPU change is disabled; non-shader modules retain their normal
// settings. Mode 0 preserves the upstream renderer. The separate stockfiles
// module verifies and selects the original shader resources before init hooks.

export namespace ENBCompat
{
    enum class Mode
    {
        Disabled = 0,   // upstream FusionFix, unchanged
        Enabled = 1,    // ENB-compatible rendering
        Auto = 2,       // Enabled when an ENB is detected in the process
    };

    enum class Profile
    {
        FusionFixDefault,
        StockENB,
    };

    #include "rendererprofile.hxx"

    struct State
    {
        Mode mode = Mode::Disabled;
        Profile profile = Profile::FusionFixDefault;
        bool detected = false;
        bool verbose = false;
        std::wstring detectedName;
        RendererCompatibilityProfile renderer;

    };

    // --- logging --------------------------------------------------------

    inline std::filesystem::path LogPath()
    {
        return GetExeModulePath() / L"ENBCompat.log";
    }

    inline void Log(std::string_view text)
    {
        static std::mutex mutex;
        static bool opened = false;

        std::scoped_lock lock(mutex);
        std::ofstream file(LogPath(), opened ? std::ios::app : std::ios::trunc);
        if (!file)
            return;
        opened = true;

        SYSTEMTIME t{};
        GetLocalTime(&t);
        file << std::setfill('0')
             << std::setw(2) << t.wHour << ':' << std::setw(2) << t.wMinute << ':'
             << std::setw(2) << t.wSecond << '.' << std::setw(3) << t.wMilliseconds
             << "  " << text << std::endl;
    }

    // --- detection ------------------------------------------------------

    // Signals that an ENB is present in this process.
    //
    // Both delivery mechanisms are covered: the wrapper build replaces d3d9.dll
    // next to the exe, the injector build loads enbseries.dll. Either way the
    // preset's data files sit next to the exe, which is what the file checks
    // look for. Any one signal is enough -- a preset with no enbseries.ini is
    // not a working preset, and d3d9.dll is deliberately not treated as a
    // signal because FusionFix ships its own proxy under that name.
    inline bool DetectENB(std::wstring& name)
    {
        ModuleList modules;
        modules.Enumerate(ModuleList::SearchLocation::LocalOnly);
        for (auto& entry : modules.m_moduleList)
        {
            auto& moduleName = std::get<std::wstring>(entry);
            if (iequals(moduleName, L"enbseries") || iequals(moduleName, L"enbhelper"))
            {
                name = moduleName + L".dll";
                return true;
            }
        }

        auto exeDir = GetExeModulePath();
        std::error_code ec;
        for (auto file : { L"enbseries.ini", L"enbeffect.fx", L"enbbloom.fx" })
        {
            if (std::filesystem::exists(exeDir / file, ec) && !ec)
            {
                name = file;
                return true;
            }
        }
        if (std::filesystem::is_directory(exeDir / L"shaderinput", ec) && !ec)
        {
            name = L"shaderinput";
            return true;
        }

        return false;
    }

    inline const char* ProfileName(Profile profile)
    {
        return profile == Profile::StockENB ? "StockENB" : "FusionFixDefault";
    }

    // --- configuration --------------------------------------------------

    // Reads [ENBCompatibility] and resolves the active profile.
    //
    // Mode=1 enforces stock shaders; per-feature overrides are intentionally
    // unsupported. Non-shader settings remain owned by their original modules.
    //
    // This runs lazily on first access rather than from an init event: the
    // rendering modules install their hooks from onInitEventAsync, which
    // dllmain dispatches *before* onInitEvent, so an event handler here would
    // be too late for the modules that need to read the profile.
    // The FusionFix ini keeps a trailing "// ..." comment on most lines, which
    // ReadInteger tolerates because stoi stops at the first non-digit but
    // ReadString hands back verbatim. Strip it before comparing a value by name.
    inline std::string TrimIniValue(std::string value)
    {
        auto comment = value.find_first_of(";");
        auto slashes = value.find("//");
        comment = std::min(comment == std::string::npos ? value.size() : comment,
                           slashes == std::string::npos ? value.size() : slashes);
        value.resize(comment);
        auto first = value.find_first_not_of(" \t\r\n");
        if (first == std::string::npos)
            return {};
        return value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1);
    }

    inline State LoadState()
    {
        State state;
        CIniReader iniReader("");

        auto modeText = TrimIniValue(iniReader.ReadString("ENBCompatibility", "Mode", "0"));
        if (iequals(modeText, "auto"))
            state.mode = Mode::Auto;
        else if (iniReader.ReadInteger("ENBCompatibility", "Mode", 0) == 2)
            state.mode = Mode::Auto;
        else if (iniReader.ReadInteger("ENBCompatibility", "Mode", 0) != 0)
            state.mode = Mode::Enabled;

        state.verbose = iniReader.ReadInteger("ENBCompatibility", "VerboseLogging", 0) != 0;

        if (state.mode == Mode::Auto)
            state.detected = DetectENB(state.detectedName);

        auto active = (state.mode == Mode::Enabled) || (state.mode == Mode::Auto && state.detected);
        state.profile = active ? Profile::StockENB : Profile::FusionFixDefault;

        // ENB mode is a strict stock-CE shader contract. Old per-feature keys
        // cannot revive FusionShaders, extra constants, or replacement passes.
        // Mode 0 retains upstream renderer defaults, regardless of stale keys.
        state.renderer = RendererCompatibilityProfile(!active);
        auto& renderer = state.renderer;
        if (state.mode == Mode::Disabled && !state.verbose)
            return state;
        if (active)
            Log("stock CE shader baseline required; all FusionFix shader changes disabled");

        std::ostringstream out;
        out << "ENBCompatibility mode=" << modeText
            << " profile=" << ProfileName(state.profile);
        if (state.mode == Mode::Auto)
        {
            out << " detected=" << (state.detected ? "yes" : "no");
            if (state.detected)
                out << " (" << std::string(state.detectedName.begin(), state.detectedName.end()) << ")";
        }
        Log(out.str());

        std::ostringstream features;
        features << "  ReplacePostFX=" << renderer.ReplacePostFX
                 << " PostProcessAA=" << renderer.PostProcessAA
                 << " AmbientOcclusion=" << renderer.AmbientOcclusion
                 << " ShadowPipelineFixes=" << renderer.ShadowPipelineFixes
                 << " FusionShaderTweaks=" << renderer.FusionShaderTweaks
                 << " SunShafts=" << renderer.SunShafts
                 << " PreAlphaDepthCopy=" << renderer.PreAlphaDepthCopy
                 << " SkyDiffuseSplit=" << renderer.SkyDiffuseSplit
                 << " ConsoleGammaBlit=" << renderer.ConsoleGammaBlit
                 << " ShaderConstantInjection=" << renderer.ShaderConstantInjection
                 << " FusionShaderPackage=" << renderer.FusionShaderPackage
                 << " ShaderPreload=" << renderer.ShaderPreload
                 << " ReflectionShaders=" << renderer.ReflectionShaders
                 << " SnowShaders=" << renderer.SnowShaders;
        Log(features.str());

        return state;
    }

    inline const State& Get()
    {
        static State state = LoadState();
        return state;
    }

    // --- accessors ------------------------------------------------------

    inline const RendererCompatibilityProfile& Renderer() { return Get().renderer; }
    inline Profile CurrentProfile()                       { return Get().profile; }
    inline Mode ConfiguredMode()                          { return Get().mode; }
    inline bool VerboseLogging()                          { return Get().verbose; }

    // True when the ENB-compatible rendering profile is in effect. Callers that
    // only need "am I in ENB mode" should use this; callers deciding whether to
    // install a specific hook should read the matching Renderer() field instead,
    // without disabling unrelated fixes or permitting mixed shader profiles.
    inline bool Active() { return CurrentProfile() == Profile::StockENB; }

    inline void LogVerbose(std::string_view text)
    {
        if (VerboseLogging())
            Log(text);
    }
}

// ENB 0.163 recognizes the stock DOF composite. Report an incompatible native
// DOF setting without changing camera/gameplay preferences or claiming a cause
// for any visual artifact. This check does not install a postfx workaround.
class ENBCompatSettingsCheck
{
public:
    ENBCompatSettingsCheck()
    {
        FusionFix::onGameInitEvent() += []()
        {
            if (!ENBCompat::Active())
                return;

            static auto dof = FusionFixSettings.GetRef("PREF_TCYC_DOF");
            if (!dof)
                return;

            auto value = dof->get();
            if (value >= FusionFixSettings.DofText.eLow)
                return;

            ENBCompat::Log("WARNING: Depth of Field is set to '"
                + std::string(value >= 0 && value < static_cast<int32_t>(FusionFixSettings.DofText.data.size())
                    ? FusionFixSettings.DofText.data[value] : "?")
                + "'. An ENB preset replaces the depth-of-field composite pass"
                " (rage_postfx#13); with DOF off the game binds the no-DOF pass"
                " (rage_postfx#29) instead, whose register layout differs, so the"
                " preset's post-processing never applies and the image comes out"
                " overexposed. Set Depth of Field to Low or higher.");
        };
    }
} ENBCompatSettingsCheck;
