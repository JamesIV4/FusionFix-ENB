// Assemble a D3D9 shaderinput text file without creating a D3D device.
// Uses the same D3DXAssembleShader API and flags (zero) recovered in ENB 0.163.

#include <d3dx9.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

int wmain(int argc, wchar_t** argv)
{
    if (argc != 3)
    {
        std::wcerr << L"usage: assemble_shader <input.txt> <new-output.cso>\n";
        return 2;
    }

    const std::filesystem::path input = argv[1];
    const std::filesystem::path output = argv[2];
    if (!std::filesystem::is_regular_file(input))
    {
        std::wcerr << L"input is not a file: " << input << L'\n';
        return 2;
    }
    if (std::filesystem::exists(output))
    {
        std::wcerr << L"output already exists: " << output << L'\n';
        return 2;
    }

    std::ifstream stream(input, std::ios::binary);
    std::vector<char> source((std::istreambuf_iterator<char>(stream)),
                             std::istreambuf_iterator<char>());
    if ((!stream && !stream.eof()) || source.empty())
    {
        std::wcerr << L"failed to read input\n";
        return 2;
    }

    ID3DXBuffer* shader = nullptr;
    ID3DXBuffer* errors = nullptr;
    const HRESULT hr = D3DXAssembleShader(source.data(), static_cast<UINT>(source.size()),
                                          nullptr, nullptr, 0, &shader, &errors);
    if (FAILED(hr))
    {
        std::cerr << "D3DXAssembleShader failed: 0x" << std::hex
                  << static_cast<unsigned long>(hr) << '\n';
        if (errors && errors->GetBufferPointer())
            std::cerr.write(static_cast<const char*>(errors->GetBufferPointer()),
                            static_cast<std::streamsize>(errors->GetBufferSize()));
        if (errors)
            errors->Release();
        if (shader)
            shader->Release();
        return 1;
    }

    std::filesystem::create_directories(output.parent_path());
    std::ofstream out(output, std::ios::binary | std::ios::out);
    out.write(static_cast<const char*>(shader->GetBufferPointer()),
              static_cast<std::streamsize>(shader->GetBufferSize()));
    const bool okay = static_cast<bool>(out);
    shader->Release();
    if (errors)
        errors->Release();
    if (!okay)
    {
        std::wcerr << L"failed to write output\n";
        return 2;
    }
    std::wcout << L"assembled " << input.filename() << L" -> " << output << L'\n';
    return 0;
}
