module;

#include <common.hxx>
#include <fstream>
#include <sstream>
#include <filesystem>

export module enbcompat;

import common;
import settings;

// ENB compatibility core.
//
// ENBSeries participates in the D3D9 path as a d3d9.dll wrapper (or an injected
// enbseries.dll) and owns the end of the frame: tone mapping, bloom, adaptation,
// AA and the final blit to the back buffer. FusionFix owns the same territory --
// it replaces the game's post-process draw call, uploads its own shader
// constants and ships a full replacement shader package. Where the two overlap,
// one of them has to stand down.
//
// This module holds the switch. It does not itself change any rendering; it
// publishes a RendererCompatibilityProfile that the rendering modules consult
// before installing their hooks, so that with the feature off the game runs the
// unmodified upstream code path rather than a guarded version of it.
//
// Nothing here auto-detects by default. Explicit modes are far easier to reason
// about while the conflict set is still being narrowed down; Mode=Auto exists
// but has to be asked for.

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
        ENBLegacy,
    };

    // The set of FusionFix rendering behaviours an external post-processor can
    // collide with. Each is a separate switch because the point of Phase 1 is to
    // find out which ones actually matter -- see research/feature-conflicts.md.
    //
    // Every field is "should FusionFix do this", so the FusionFixDefault profile
    // is all-true and matches upstream exactly.
    struct RendererCompatibilityProfile
    {
        // Replace the game's rage_postfx draw with FusionFix's own chain
        // (tone mapping, bloom handling, AA, sun shafts). This is the single
        // biggest overlap with ENB, which wants to own the same pass.
        bool ReplacePostFX = true;

        // The FXAA / SMAA passes inside that chain. ENB presets normally bring
        // their own AA and expect an unfiltered image.
        bool PostProcessAA = true;

        // The ambient-occlusion pass appended after ped/vehicle fake shadows.
        bool AmbientOcclusion = true;

        // FusionFix changes the cascade-atlas/G-buffer formats, cascade ranges
        // and shadow matrices as one contract with its replacement lighting
        // shaders. Stock shaders need the stock resource layout.
        bool ShadowPipelineFixes = true;

        // Executable/render-state tweaks authored for FusionShaders: reflection
        // multiplier, console-gamma contrast offset and DXVK adaptive-state
        // suppression. Stock D3D9 shaders should retain the game's behavior.
        bool FusionShaderTweaks = true;

        // Sun shafts (prepass/draw/add) inside the post-process chain.
        bool SunShafts = true;

        // The pre-alpha depth copy used so depth-driven effects see through
        // glass. Costs an extra depth-sized render target.
        bool PreAlphaDepthCopy = true;

        // The second sky draw that splits atmospheric scattering into the
        // GBuffer diffuse target.
        bool SkyDiffuseSplit = true;

        // The console-gamma blit, which copies the current render target
        // through a gamma shader onto the real back buffer at EndScene. That is
        // the same moment ENB applies its own effect, and whichever runs second
        // decides what reaches the screen.
        bool ConsoleGammaBlit = true;

        // Uploads to c208..c223 (pixel) and c227..c237 (vertex). The replacement
        // package reads them, as does FusionFix-only gta_trees_extended, which
        // remains reachable in the otherwise-stock ENB package.
        bool ShaderConstantInjection = true;

        // Whether the game should load the FusionFix replacement shader
        // package. Running an old ENB generally means running the stock
        // shaders, since ENB matches shaders by bytecode hash and every shader
        // in the FusionFix package has a different one.
        //
        // Turning this off does not delete or move anything. FusionFix normally
        // collapses the game's six GPU-specific shader-variant folders onto
        // win32_30, which is the one folder its own package overlays; with this
        // off, the collapse targets StockShaderFolder instead, which nothing
        // overlays, so the game loads the stock shaders straight out of
        // common/shaders. Flip it back and the FusionFix package is live again.
        bool FusionShaderPackage = true;
    };

    struct State
    {
        Mode mode = Mode::Disabled;
        Profile profile = Profile::FusionFixDefault;
        bool detected = false;
        bool verbose = false;
        std::wstring detectedName;
        RendererCompatibilityProfile renderer;

        // Which of the game's shader-variant folders to load stock shaders
        // from when FusionShaderPackage is off. The six differ only in how
        // they were compiled for a given GPU generation; measured against CE
        // 1.2.0.59, win32_30 and win32_30_nv8 are byte-identical for 1688 of
        // 1689 shaders, so the choice barely matters -- but it is configurable
        // because ENB's hash was computed against whichever one the preset's
        // author happened to be running, and that is not knowable from here.
        std::string stockShaderFolder = "win32_30_nv8";
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
        return profile == Profile::ENBLegacy ? "ENBLegacy" : "FusionFixDefault";
    }

    // What the game will actually load from a given shader-variant folder.
    //
    // The FusionShaders build stamps a "FusionShader" marker into every shader
    // it rewrites (as def c219 / def c230), so reading a container is enough to
    // tell a replacement from the stock original. Worth knowing because the two
    // halves of the install are configured separately -- the .asi reads this
    // ini, the shader package is a folder the user copies in -- and a mismatch
    // between them is a silent and very confusing failure.
    //
    // Several containers are probed rather than one, because a selective
    // package deliberately mixes the two: FusionFix shaders everywhere except
    // the containers an ENB preset needs to recognise.
    enum class ShaderPackage { Unknown, Stock, FusionFix, Mixed };

    inline ShaderPackage DetectShaderPackage(const std::string& folder)
    {
        // gta_default is one an ENB preset is likely to want from stock;
        // the next two are untargeted controls, and gta_trees_extended exposes
        // the required FusionFix-only exception instead of logging all-stock.
        static const wchar_t* probes[] = {
            L"gta_default.fxc", L"gta_normal_spec.fxc", L"gta_ped.fxc",
            L"gta_trees_extended.fxc",
        };

        auto dir = GetExeModulePath() / L"update" / L"common" / L"shaders"
            / std::filesystem::path(folder);

        static const std::string marker = "FusionShader";
        auto fusion = 0, stock = 0;
        for (auto probe : probes)
        {
            std::error_code ec;
            auto path = dir / probe;
            if (!std::filesystem::exists(path, ec) || ec)
            {
                // Not overlaid, so this container comes from common/shaders.
                stock++;
                continue;
            }

            std::ifstream file(path, std::ios::binary);
            if (!file)
                continue;

            std::string buffer((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            (buffer.find(marker) != std::string::npos ? fusion : stock)++;
        }

        if (!fusion && !stock)
            return ShaderPackage::Unknown;
        if (!fusion)
            return ShaderPackage::Stock;
        if (!stock)
            return ShaderPackage::FusionFix;
        return ShaderPackage::Mixed;
    }

    // --- configuration --------------------------------------------------

    // Reads [ENBCompatibility] and resolves the active profile.
    //
    // Per-feature keys default to the profile's own default, so a plain Mode=1
    // gives the whole ENB-compatible profile and an individual key only has to
    // be written when bisecting one feature at a time.
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
        else if (iniReader.ReadInteger("ENBCompatibility", "Mode", 0) != 0)
            state.mode = Mode::Enabled;

        state.verbose = iniReader.ReadInteger("ENBCompatibility", "VerboseLogging", 0) != 0;

        if (state.mode == Mode::Auto)
            state.detected = DetectENB(state.detectedName);

        auto active = (state.mode == Mode::Enabled) || (state.mode == Mode::Auto && state.detected);
        state.profile = active ? Profile::ENBLegacy : Profile::FusionFixDefault;

        auto& renderer = state.renderer;
        if (active)
        {
            // Defaults for ENB mode: FusionFix stands down from everything that
            // reaches into the end of the frame or depends on the replacement
            // shader package, and keeps everything else.
            renderer.ReplacePostFX = false;
            renderer.PostProcessAA = false;
            renderer.AmbientOcclusion = false;
            renderer.ShadowPipelineFixes = false;
            renderer.FusionShaderTweaks = false;
            renderer.SunShafts = false;
            renderer.PreAlphaDepthCopy = false;
            renderer.SkyDiffuseSplit = false;
            renderer.ConsoleGammaBlit = false;
            // gta_trees_extended still needs c221/c233 in the stock package.
            // Stock shaders do not read these high registers, so retaining the
            // provider is harmless for them and required for correct tree alpha.
            renderer.ShaderConstantInjection = true;
            renderer.FusionShaderPackage = false;
        }

        // Per-feature overrides. Read unconditionally so that a bisect can also
        // switch a single feature back on in ENB mode, or off in normal mode.
        auto readFeature = [&iniReader](const char* key, bool& value)
        {
            value = iniReader.ReadInteger("ENBCompatibility", key, value ? 1 : 0) != 0;
        };
        readFeature("ReplacePostFX", renderer.ReplacePostFX);
        readFeature("PostProcessAA", renderer.PostProcessAA);
        readFeature("AmbientOcclusion", renderer.AmbientOcclusion);
        readFeature("ShadowPipelineFixes", renderer.ShadowPipelineFixes);
        readFeature("FusionShaderTweaks", renderer.FusionShaderTweaks);
        readFeature("SunShafts", renderer.SunShafts);
        readFeature("PreAlphaDepthCopy", renderer.PreAlphaDepthCopy);
        readFeature("SkyDiffuseSplit", renderer.SkyDiffuseSplit);
        readFeature("ConsoleGammaBlit", renderer.ConsoleGammaBlit);
        readFeature("ShaderConstantInjection", renderer.ShaderConstantInjection);
        readFeature("FusionShaderPackage", renderer.FusionShaderPackage);

        auto folder = TrimIniValue(iniReader.ReadString("ENBCompatibility", "StockShaderFolder", ""));
        if (!folder.empty())
            state.stockShaderFolder = folder;

        if (state.mode == Mode::Disabled && !state.verbose)
            return state;

        if (!renderer.FusionShaderPackage)
        {
            Log("stock shaders requested: shader-variant lookups redirected to common/shaders/"
                + state.stockShaderFolder);

            // The one shader FusionFix genuinely adds rather than replaces.
            // Its content packages reference it, so it has to be reachable from
            // whichever folder the lookups now point at, or the game throws a
            // resource error before the main menu.
            auto extended = GetExeModulePath() / L"update" / L"common" / L"shaders"
                / std::filesystem::path(state.stockShaderFolder) / L"gta_trees_extended.fxc";
            std::error_code ec;
            if (!std::filesystem::exists(extended, ec) || ec)
            {
                Log("  WARNING: gta_trees_extended.fxc is missing from update/common/shaders/"
                    + state.stockShaderFolder
                    + ". FusionFix content that references it will fail to load."
                    " Run tools/shader_dump/make_vanilla_package.py --stage-extras.");
            }
        }

        auto activeFolder = renderer.FusionShaderPackage ? std::string("win32_30")
                                                         : state.stockShaderFolder;
        auto installed = DetectShaderPackage(activeFolder);
        Log("shaders loaded from " + activeFolder + ": "
            + (installed == ShaderPackage::FusionFix ? "FusionFix"
             : installed == ShaderPackage::Stock ? "stock"
             : installed == ShaderPackage::Mixed ? "mixed (FusionFix additions/selective package)" : "unknown"));

        // A mixed package is a deliberate arrangement, not a mistake: FusionFix
        // shaders everywhere except the containers an ENB preset needs to
        // recognise. It does mean the constant uploads are still required, since
        // most of the FusionFix shaders are still there to read them.
        if (installed == ShaderPackage::Mixed && !renderer.ShaderConstantInjection)
        {
            Log("  WARNING: a selective package is installed but ShaderConstantInjection is off."
                " The FusionFix shaders that remain read c208..c223 and c227..c237,"
                " and nothing will be writing them.");
        }
        else if (installed == ShaderPackage::FusionFix && !renderer.ShaderConstantInjection)
        {
            Log("  WARNING: the FusionFix shader package is loaded but ShaderConstantInjection"
                " is off. Those shaders read c208..c223 and c227..c237;"
                " see tools/shader_dump/make_vanilla_package.py");
        }
        else if (installed == ShaderPackage::Stock && renderer.ShaderConstantInjection)
        {
            Log("  note: stock shaders are loaded, so the constant uploads have no reader."
                " Harmless, but ShaderConstantInjection = 0 saves the work.");
        }

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
                 << " FusionShaderPackage=" << renderer.FusionShaderPackage;
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
    inline const std::string& StockShaderFolder()         { return Get().stockShaderFolder; }

    // True when the ENB-compatible rendering profile is in effect. Callers that
    // only need "am I in ENB mode" should use this; callers deciding whether to
    // install a specific hook should read the matching Renderer() field instead,
    // so that a single feature can be toggled during a bisect.
    inline bool Active() { return CurrentProfile() == Profile::ENBLegacy; }

    inline void LogVerbose(std::string_view text)
    {
        if (VerboseLogging())
            Log(text);
    }
}

// Depth of field has to be on for an ENB preset's post-process replacement to
// apply at all, and nothing about the symptom says so.
//
// GTA IV's rage_postfx.fxc holds 28 passes. The final composite exists as a
// depth-of-field variant (slot 13) and a no-DOF variant (slot 29), and the two
// have different register layouts -- slot 29 drops dofDist and BloomSampler and
// shifts everything after them down by one. ENBSeries matches a shader by a
// single hash of its bytecode, so a preset can only ever carry a replacement
// for one of them, and every GTA IV preset examined targets the DOF variant.
//
// With DOF set to Off or Cutscenes Only the game binds slot 29, no hash
// matches, the game's own tone mapping runs, and ENB stacks its bloom and
// adaptation on top of an already tone-mapped image. It looks like a washed-out
// overexposed mess and gives no hint that a menu setting is responsible.
//
// Confirmed by capture: indoors bound rage_postfx#13, outdoors #29, and the
// preset's effect visibly applied only in the first case.
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
