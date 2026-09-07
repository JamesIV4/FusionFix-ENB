#include <cassert>
#include <algorithm>
#include <iostream>
#include <set>
namespace ENBCompat {
#include "../../source/enb_compat/rendererprofile.hxx"
}
#include "../../source/enb_compat/stockfiles.hxx"

int main()
{
    using Profile = ENBCompat::RendererCompatibilityProfile;
    constexpr auto fields = std::array{
        &Profile::ReplacePostFX, &Profile::PostProcessAA, &Profile::AmbientOcclusion,
        &Profile::ShadowPipelineFixes, &Profile::FusionShaderTweaks, &Profile::SunShafts,
        &Profile::PreAlphaDepthCopy, &Profile::SkyDiffuseSplit, &Profile::ConsoleGammaBlit,
        &Profile::ShaderConstantInjection, &Profile::FusionShaderPackage,
        &Profile::ShaderPreload, &Profile::ReflectionShaders, &Profile::SnowShaders,
    };
    for (auto member : fields) {
        assert(Profile{}.*member);
        assert(!(Profile{false}.*member));
    }
    std::set<std::wstring> paths;
    size_t containers = 0;
    for (const auto& file : StockCE::Files) {
        assert(file.sha256.size() == 64);
        assert(file.path.find(L"extended") == std::wstring_view::npos);
        if (file.path.ends_with(L".fxc")) ++containers;
        for (const auto& logical : StockCE::LogicalPaths(file.path)) {
            assert(logical.starts_with(L"common/shaders/"));
            assert(paths.insert(logical).second);
        }
    }
    assert(std::size(StockCE::Files) == 339 && containers == 102 && paths.size() == 849);
    const std::filesystem::path cache = L"stock-cache";
    auto exact = [&](const std::filesystem::path& path) -> std::string {
        auto relative = path.lexically_relative(cache).generic_wstring();
        for (const auto& file : StockCE::Files)
            if (file.path == relative) return std::string(file.sha256);
        return {};
    };
    std::wstring failure;
    assert(StockCE::Verify(cache, exact, failure));
    assert(!StockCE::Verify(cache, [&](const auto& path) {
        return path.filename() == L"preload.list" ? std::string(64, '0') : exact(path);
    }, failure));
    assert(failure == L"preload.list");
    std::cout << "PASS: all 14 shader features disabled in ENB mode; normal defaults retained; "
                 "339 exact stock files, 849 unique routes, changed baseline rejected.\n";
}
