// Inspect text or compiled D3D9 effects with the original Microsoft runtime.
// No game, ENB wrapper, or preset ASI is loaded. See README.md for building.
#include <windows.h>
#include <d3d9.h>
#include <d3dx9.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

static void Check(HRESULT hr, const char* operation)
{
    if (FAILED(hr)) {
        std::cerr << operation << " failed: 0x" << std::hex << unsigned(hr) << '\n';
        throw std::runtime_error(operation);
    }
}

static void SaveBuffer(const fs::path& path, ID3DXBuffer* buffer)
{
    std::ofstream out(path, std::ios::binary);
    out.write(static_cast<const char*>(buffer->GetBufferPointer()), buffer->GetBufferSize());
    if (!out) throw std::runtime_error("Cannot write output");
}

static void SaveShader(const fs::path& path, const DWORD* code)
{
    if (!code) return;
    std::ofstream out(path.string() + ".cso", std::ios::binary);
    out.write(reinterpret_cast<const char*>(code), D3DXGetShaderSize(code));
    if (!out) throw std::runtime_error("Cannot write shader");
    ID3DXBuffer* assembly = nullptr;
    Check(D3DXDisassembleShader(code, FALSE, nullptr, &assembly), "DisassembleShader");
    SaveBuffer(path.string() + ".asm", assembly);
    assembly->Release();
}

int wmain(int argc, wchar_t** argv)
{
    if (argc != 3 && !(argc == 4 && std::wstring(argv[3]) == L"--hal")) {
        std::cerr << "Usage: inspect_effect.exe <effect.fx> <new-output-directory> [--hal]\n";
        return 2;
    }
    IDirect3D9* d3d = nullptr;
    IDirect3DDevice9* device = nullptr;
    ID3DXEffect* effect = nullptr;
    HWND window = nullptr;
    int result = 1;
    try {
        const fs::path input = fs::absolute(argv[1]), output = fs::absolute(argv[2]);
        if (fs::exists(output)) throw std::runtime_error("Output already exists");
        // A private, never-shown window avoids touching the user's game/session.
        window = CreateWindowW(L"STATIC", L"Effect inspector", WS_OVERLAPPED,
            0, 0, 16, 16, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
        if (!window) throw std::runtime_error("CreateWindow");
        d3d = Direct3DCreate9(D3D_SDK_VERSION);
        if (!d3d) throw std::runtime_error("Direct3DCreate9");
        D3DPRESENT_PARAMETERS pp{};
        pp.Windowed = TRUE;
        pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
        pp.hDeviceWindow = window;
        pp.BackBufferWidth = pp.BackBufferHeight = 16;
        // NULLREF loads/reflects bytecode without rendering. Try HAL if unavailable.
        const bool hal = argc == 4;
        HRESULT hr = d3d->CreateDevice(0, hal ? D3DDEVTYPE_HAL : D3DDEVTYPE_NULLREF, window,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING, &pp, &device);
        if (FAILED(hr) && !hal) hr = d3d->CreateDevice(0, D3DDEVTYPE_HAL, window,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING, &pp, &device);
        Check(hr, "CreateDevice");
        ID3DXBuffer* errors = nullptr;
        hr = D3DXCreateEffectFromFileW(device, input.c_str(), nullptr, nullptr,
            0, nullptr, &effect, &errors);
        if (errors) {
            std::cerr << static_cast<const char*>(errors->GetBufferPointer()) << '\n';
            errors->Release();
        }
        Check(hr, "CreateEffectFromFile");
        fs::create_directories(output);
        std::wofstream runtime(output / "runtime.tsv");
        for (const auto* name : { L"d3d9.dll", L"d3dx9_43.dll" }) {
            wchar_t modulePath[32768]{};
            if (!GetModuleFileNameW(GetModuleHandleW(name), modulePath, 32768))
                throw std::runtime_error("Cannot identify loaded runtime");
            runtime << name << L'\t' << modulePath << L'\n';
        }
        D3DDEVICE_CREATION_PARAMETERS creation{};
        Check(device->GetCreationParameters(&creation), "GetCreationParameters");
        runtime << L"device_type\t" << creation.DeviceType << L'\n';
        if (!runtime) throw std::runtime_error("Cannot write runtime evidence");
        ID3DXBuffer* assembly = nullptr;
        Check(D3DXDisassembleEffect(effect, FALSE, &assembly), "DisassembleEffect");
        SaveBuffer(output / "effect.asm", assembly);
        assembly->Release();
        D3DXEFFECT_DESC desc{};
        Check(effect->GetDesc(&desc), "GetDesc");
        std::ofstream manifest(output / "interface.tsv");
        manifest << "kind\tname\tsemantic\ttype\tclass\trows\tcolumns\telements\tbytes\n";
        for (UINT i = 0; i < desc.Parameters; ++i) {
            D3DXPARAMETER_DESC p{};
            Check(effect->GetParameterDesc(effect->GetParameter(nullptr, i), &p), "ParameterDesc");
            manifest << "parameter\t" << p.Name << '\t' << (p.Semantic ? p.Semantic : "")
                << '\t' << p.Type << '\t' << p.Class << '\t' << p.Rows << '\t'
                << p.Columns << '\t' << p.Elements << '\t' << p.Bytes << '\n';
        }
        UINT passes = 0;
        std::ofstream validation(output / "validation.tsv");
        validation << "technique\tvalidate_hresult\tbegin_hresult\tpasses_bound\n";
        for (UINT i = 0; i < desc.Techniques; ++i) {
            auto technique = effect->GetTechnique(i);
            D3DXTECHNIQUE_DESC t{};
            Check(effect->GetTechniqueDesc(technique, &t), "TechniqueDesc");
            manifest << "technique\t" << t.Name << '\n';
            const HRESULT valid = effect->ValidateTechnique(technique);
            Check(valid, "ValidateTechnique");
            Check(effect->SetTechnique(technique), "SetTechnique");
            UINT boundPasses = 0;
            const HRESULT begin = effect->Begin(&boundPasses, 0);
            Check(begin, "Begin");
            for (UINT j = 0; j < boundPasses; ++j) {
                Check(effect->BeginPass(j), "BeginPass");
                Check(effect->EndPass(), "EndPass");
            }
            Check(effect->End(), "End");
            validation << t.Name << '\t' << unsigned(valid) << '\t'
                << unsigned(begin) << '\t' << boundPasses << '\n';
            for (UINT j = 0; j < t.Passes; ++j) {
                D3DXPASS_DESC p{};
                Check(effect->GetPassDesc(effect->GetPass(technique, j), &p), "PassDesc");
                const auto stem = std::to_string(i) + "_" + std::to_string(j);
                manifest << "pass\t" << stem << '\t' << (p.Name ? p.Name : "") << '\n';
                SaveShader(output / (stem + "_ps"), p.pPixelShaderFunction);
                SaveShader(output / (stem + "_vs"), p.pVertexShaderFunction);
                ++passes;
            }
        }
        if (!manifest || !validation) throw std::runtime_error("Cannot write manifest");
        std::cout << "Loaded with stock D3DX9: " << desc.Parameters << " parameters, "
            << desc.Techniques << " techniques, " << passes << " passes\n";
        result = 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; }
    if (effect) effect->Release();
    if (device) device->Release();
    if (d3d) d3d->Release();
    if (window) DestroyWindow(window);
    return result;
}
