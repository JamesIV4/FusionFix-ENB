#pragma once

// Included inside ENBCompat. These flags govern shader code and its GPU
// resource/constant contracts only. Gameplay/camera fixes never consult them.
struct RendererCompatibilityProfile
{
    bool ReplacePostFX, PostProcessAA, AmbientOcclusion, ShadowPipelineFixes;
    bool FusionShaderTweaks, SunShafts, PreAlphaDepthCopy, SkyDiffuseSplit;
    bool ConsoleGammaBlit, ShaderConstantInjection, FusionShaderPackage;
    bool ShaderPreload, ReflectionShaders, SnowShaders;

    explicit constexpr RendererCompatibilityProfile(bool enabled = true)
        : ReplacePostFX(enabled), PostProcessAA(enabled), AmbientOcclusion(enabled),
          ShadowPipelineFixes(enabled), FusionShaderTweaks(enabled), SunShafts(enabled),
          PreAlphaDepthCopy(enabled), SkyDiffuseSplit(enabled), ConsoleGammaBlit(enabled),
          ShaderConstantInjection(enabled), FusionShaderPackage(enabled),
          ShaderPreload(enabled), ReflectionShaders(enabled), SnowShaders(enabled) {}
};
