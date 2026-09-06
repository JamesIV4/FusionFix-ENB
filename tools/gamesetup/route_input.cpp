// Bounded movement primitive for the user-requested GTA IV outdoor test route.
// No window activation, game memory access, screenshots or general UI commands.
// Requires a foreground GTAIV.exe window and releases all keys on every exit.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <string>
#include <vector>
#include <iostream>
#include <algorithm>

bool send_scan(WORD scan, bool up)
{
    INPUT input{};
    input.type = INPUT_KEYBOARD;
    input.ki.wScan = scan;
    input.ki.dwFlags = KEYEVENTF_SCANCODE | (up ? KEYEVENTF_KEYUP : 0);
    return SendInput(1, &input, sizeof(input)) == 1;
}

int wmain(int argc, wchar_t** argv)
{
    if (argc != 4) { std::cerr << "usage: route_input <observed-window-id> <forward|left|right|back|jump|forward_jump> <milliseconds<=5000>\n"; return 2; }
    HWND window = reinterpret_cast<HWND>(static_cast<uintptr_t>(_wcstoui64(argv[1], nullptr, 10)));
    int duration = _wtoi(argv[3]);
    std::wstring action = argv[2];
    std::vector<WORD> keys;
    if (action == L"forward") keys = {0x11};
    else if (action == L"left") keys = {0x1e};
    else if (action == L"right") keys = {0x20};
    else if (action == L"back") keys = {0x1f};
    else if (action == L"jump") keys = {0x39};
    else if (action == L"forward_jump") keys = {0x11, 0x39};
    else return 2;
    if (duration < 1 || duration > 5000 || !IsWindow(window) || GetForegroundWindow() != window) { std::cerr << "Game is not foreground, or invalid duration\n"; return 2; }
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!process) return 2;
    wchar_t path[32768]{}; DWORD length = std::size(path);
    bool queried = QueryFullProcessImageNameW(process, 0, path, &length) != 0;
    CloseHandle(process);
    std::wstring name(path);
    auto separator = name.find_last_of(L"\\/");
    if (separator != std::wstring::npos) name.erase(0, separator + 1);
    if (!queried || _wcsicmp(name.c_str(), L"GTAIV.exe") != 0) { std::cerr << "Target is not GTAIV.exe\n"; return 2; }
    auto start = GetTickCount64();
    bool okay = true;
    for (auto key : keys) okay = send_scan(key, false) && okay;
    while (okay && GetTickCount64() - start < static_cast<ULONGLONG>(duration))
    {
        if (GetForegroundWindow() != window || (GetAsyncKeyState(VK_ESCAPE) & 0x8000)) { okay = false; break; }
        Sleep(5);
    }
    for (auto it = keys.rbegin(); it != keys.rend(); ++it) okay = send_scan(*it, true) && okay;
    std::cout << "elapsed_ms=" << GetTickCount64() - start << " completed=" << okay << '\n';
    return okay ? 0 : 1;
}
