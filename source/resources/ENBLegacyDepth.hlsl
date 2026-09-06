// Decode FusionFix's log depth, then encode stock GTA IV projection depth.
// c209 provider: {1/near, 1/log2(far/near), far/near, near}.
// The caller validates clip planes and supplies them in c0/c1 for this pass.
float4 ClipPlanes : register(c0);
float4 LogDepth : register(c1);
sampler2D ModernDepth : register(s1);

float4 main(float2 uv : TEXCOORD0) : COLOR0
{
    float logDepth = tex2D(ModernDepth, uv).x;
    float viewDepth = LogDepth.w * pow(abs(LogDepth.z), logDepth);
    float nearClip = ClipPlanes.x;
    float farClip = ClipPlanes.y;
    float depth = farClip / (farClip - nearClip)
                - (farClip * nearClip) / ((farClip - nearClip) * viewDepth);
    return float4(saturate(depth), 0, 0, 1);
}
