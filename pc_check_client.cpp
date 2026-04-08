// PC Check Client - Compiles to a standalone EXE
// This collects system info and sends it to a Discord webhook
//
// Compile with: g++ -o pc_check.exe pc_check_client.cpp -lws2_32
// Or use any C++ compiler with Windows sockets support

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #include <iphlpapi.h>
    #pragma comment(lib, "ws2_32.lib")
    #pragma comment(lib, "iphlpapi.lib")
    #pragma comment(lib, "winmm.lib")
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <netdb.h>
    typedef int SOCKET;
    #define SOCKET_ERROR -1
    #define INVALID_SOCKET -1
#endif

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <ctime>
#include <iomanip>
#include <algorithm>
#include <locale>
#include <codecvt>

// Windows headers
#ifdef _WIN32
    #include <windows.h>
    #include <shlobj.h>
    #include <LM.h>
    #include <tlhelp32.h>
    #include <comdef.h>
#endif

// ======================== CONFIGURATION ========================
// Set this to your webhook URL
std::string WEBHOOK_URL = "YOUR_WEBHOOK_URL_HERE";

// Check ID to identify this check
std::string CHECK_ID = "";

// User ID from command line argument
std::string USER_ID = "";

// ======================== UTILITIES ========================

std::string executeCommand(const char* cmd) {
    char buffer[128];
    std::string result = "";

    #ifdef _WIN32
        FILE* pipe = _popen(cmd, "r");
    #else
        FILE* pipe = popen(cmd, "r");
    #endif

    if (!pipe) return "";

    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        result += buffer;
    }

    #ifdef _WIN32
        _pclose(pipe);
    #else
        pclose(pipe);
    #endif

    // Remove trailing whitespace
    while (!result.empty() && (result.back() == '\n' || result.back() == '\r' || result.back() == ' ')) {
        result.pop_back();
    }

    return result;
}

std::string getenv_safe(const char* name) {
    #ifdef _WIN32
        char buf[32767];
        if (GetEnvironmentVariableA(name, buf, sizeof(buf)) > 0) {
            return std::string(buf);
        }
    #else
        if (const char* val = std::getenv(name)) {
            return std::string(val);
        }
    #endif
    return "";
}

std::string getMACAddress() {
    std::string mac = "Unknown";

    #ifdef _WIN32
        PIP_ADAPTER_INFO pAdapterInfo;
        PIP_ADAPTER_INFO pAdapter = NULL;
        DWORD dwBufLen = sizeof(IP_ADAPTER_INFO);
        DWORD dwStatus;

        pAdapterInfo = (IP_ADAPTER_INFO*)malloc(sizeof(IP_ADAPTER_INFO));
        if (pAdapterInfo == NULL) return "Memory allocation failed";

        dwStatus = GetAdaptersInfo(pAdapterInfo, &dwBufLen);
        if (dwStatus == ERROR_BUFFER_OVERFLOW) {
            free(pAdapterInfo);
            pAdapterInfo = (IP_ADAPTER_INFO*)malloc(dwBufLen);
            if (pAdapterInfo == NULL) return "Memory allocation failed";
            dwStatus = GetAdaptersInfo(pAdapterInfo, &dwBufLen);
        }

        if (dwStatus == ERROR_SUCCESS) {
            pAdapter = pAdapterInfo;
            while (pAdapter) {
                if (pAdapter->AddressLength == 6) {
                    char mac_str[18];
                    sprintf(mac_str, "%02X:%02X:%02X:%02X:%02X:%02X",
                        pAdapter->Address[0], pAdapter->Address[1],
                        pAdapter->Address[2], pAdapter->Address[3],
                        pAdapter->Address[4], pAdapter->Address[5]);
                    mac = mac_str;
                    break;
                }
                pAdapter = pAdapter->Next;
            }
        }
        free(pAdapterInfo);
    #endif

    return mac;
}

std::string getPublicIP() {
    std::string ip = "Unable to get";

    #ifdef _WIN32
        HINTERNET hInternet, hConnect;
        hInternet = InternetOpenA("PCCheck/1.0", INTERNET_OPEN_TYPE_PRECONFIG, NULL, NULL, 0);
        if (hInternet) {
            hConnect = InternetOpenUrlA(hInternet, "https://api.ipify.org", NULL, 0, INTERNET_FLAG_RELOAD, 0);
            if (hConnect) {
                char buffer[256];
                DWORD bytesRead = 0;
                if (InternetReadFile(hConnect, buffer, sizeof(buffer) - 1, &bytesRead)) {
                    buffer[bytesRead] = '\0';
                    ip = buffer;
                }
                InternetCloseHandle(hConnect);
            }
            InternetCloseHandle(hInternet);
        }
    #else
        ip = executeCommand("curl -s ifconfig.me");
    #endif

    return ip;
}

std::string getCPUName() {
    #ifdef _WIN32
        std::ifstream file("C:\\ProgramData\\ packageing\\CPUInfo.txt");
        if (file.is_open()) {
            std::string line;
            while (std::getline(file, line)) {
                if (line.find("processor") != std::string::npos) {
                    std::getline(file, line);
                    break;
                }
            }
            file.close();
        }

        // Try registry
        HKEY hKey;
        char cpuName[256];
        DWORD len = sizeof(cpuName);
        if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
            if (RegQueryValueExA(hKey, "ProcessorNameString", NULL, NULL, (LPBYTE)cpuName, &len) == ERROR_SUCCESS) {
                RegCloseKey(hKey);
                return std::string(cpuName);
            }
            RegCloseKey(hKey);
        }
        return "Unknown";
    #else
        return executeCommand("cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2");
    #endif
}

std::string getGPUName() {
    #ifdef _WIN32
        std::string gpu = executeCommand("wmic path win32_VideoController get name");
        // Remove whitespace and newlines
        gpu.erase(std::remove_if(gpu.begin(), gpu.end(), ::isspace), gpu.end());
        if (gpu == "name" || gpu.empty()) return "Unknown";
        return gpu;
    #else
        return executeCommand("lspci | grep -i vga | cut -d: -f3");
    #endif
}

std::string getRAMInfo() {
    #ifdef _WIN32
        MEMORYSTATUSEX mem;
        mem.dwLength = sizeof(mem);
        if (GlobalMemoryStatusEx(&mem)) {
            std::ostringstream oss;
            oss << std::fixed << std::setprecision(0)
                << (mem.ullTotalPhys / (1024.0 * 1024.0 * 1024.0)) << " GB";
            return oss.str();
        }
        return "Unknown";
    #else
        return executeCommand("free -h | grep Mem | awk '{print $2}'");
    #endif
}

std::string getOSVersion() {
    #ifdef _WIN32
        OSVERSIONINFOEX osvi;
        ZeroMemory(&osvi, sizeof(OSVERSIONINFOEX));
        osvi.dwOSVersionInfoSize = sizeof(OSVERSIONINFOEX);
        if (GetVersionExA((OSVERSIONINFOA*)&osvi)) {
            std::ostringstream oss;
            oss << "Windows " << osvi.dwMajorVersion << "." << osvi.dwMinorVersion;

            if (osvi.wProductType == VER_NT_WORKSTATION) {
                if (osvi.dwMajorVersion == 10 && osvi.dwMinorVersion == 0) {
                    oss << " (Windows 10/11)";
                }
            } else {
                oss << " Server";
            }
            return oss.str();
        }
        return "Unknown Windows";
    #else
        return executeCommand("uname -sr");
    #endif
}

std::string getHostname() {
    char hostname[256];
    if (gethostname(hostname, sizeof(hostname)) == 0) {
        return std::string(hostname);
    }
    return "Unknown";
}

std::string getUsername() {
    #ifdef _WIN32
        char username[256];
        DWORD size = sizeof(username);
        if (GetUserNameA(username, &size)) {
            return std::string(username);
        }
    #else
        char* user = std::getenv("USER");
        if (user) return std::string(user);
        user = std::getenv("USERNAME");
        if (user) return std::string(user);
    #endif
    return "Unknown";
}

std::string getCurrentTimestamp() {
    time_t now = time(nullptr);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", localtime(&now));
    return std::string(buf);
}

std::string getUptime() {
    #ifdef _WIN32
        std::string uptime = executeCommand("net stats srv | find \"Statistics\"");
        if (!uptime.empty()) return uptime;
        return "Unknown";
    #else
        return executeCommand("uptime -p");
    #endif
}

// Check for suspicious processes
std::vector<std::string> checkSuspiciousProcesses() {
    std::vector<std::string> found;

    #ifdef _WIN32
        std::string suspicious[] = {
            "cheatengine", "cheat engine", "artmoney", "gamecih",
            "igg", "cr injector", "xenos", "extreme injector",
            "vape", "novoline", "freefire", "pubg", "valorant",
            "fortnite", "aimbot", "wallhack", "triggerbot"
        };

        // Create toolhelp snapshot
        HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snapshot == INVALID_HANDLE_VALUE) return found;

        PROCESSENTRY32 pe;
        pe.dwSize = sizeof(PROCESSENTRY32);

        if (Process32First(snapshot, &pe)) {
            do {
                std::string procName = pe.szExeFile;
                std::transform(procName.begin(), procName.end(), procName.begin(), ::tolower);

                for (const auto& sus : suspicious) {
                    if (procName.find(sus) != std::string::npos) {
                        found.push_back(pe.szExeFile);
                        break;
                    }
                }
            } while (Process32Next(snapshot, &pe));
        }
        CloseHandle(snapshot);
    #endif

    return found;
}

// Check for VM
bool isVirtualMachine() {
    #ifdef _WIN32
        std::string indicators[] = {
            "vmware", "virtualbox", "hyper-v", "parallels", "qemu", "kvm",
            "hyperv", "vbox", "qemu-", "kvm-", "redhat", "vmware-"
        };

        std::string bios = executeCommand("wmic bios get serialnumber");
        std::transform(bios.begin(), bios.end(), bios.begin(), ::tolower);

        for (const auto& ind : indicators) {
            if (bios.find(ind) != std::string::npos) {
                return true;
            }
        }

        std::string system = executeCommand("wmic computersystem get model");
        std::transform(system.begin(), system.end(), system.begin(), ::tolower);
        for (const auto& ind : indicators) {
            if (system.find(ind) != std::string::npos) {
                return true;
            }
        }
    #endif
    return false;
}

// Check for USB devices
std::vector<std::string> getUSBDevices() {
    std::vector<std::string> devices;

    #ifdef _WIN32
        std::string output = executeCommand("wmic path win32_USBControllerDevice get Dependent");
        std::istringstream stream(output);
        std::string line;
        while (std::getline(stream, line)) {
            if (line.find("USB") != std::string::npos && line.find("Device") == std::string::npos) {
                line.erase(std::remove_if(line.begin(), line.end(), ::isspace), line.end());
                if (!line.empty() && line.length() > 5) {
                    devices.push_back(line);
                }
            }
        }
    #endif

    return devices;
}

// ======================== HTTP REQUEST ========================

int sendWebhook(const std::string& url, const std::string& jsonPayload) {
    // Parse URL
    std::string host, path;
    int port = 443;

    // Simple URL parsing
    size_t proto_end = url.find("://");
    size_t host_start = (proto_end != std::string::npos) ? proto_end + 3 : 0;
    size_t path_start = url.find("/", host_start);

    if (path_start != std::string::npos) {
        host = url.substr(host_start, path_start - host_start);
        path = url.substr(path_start);
    } else {
        host = url.substr(host_start);
        path = "/";
    }

    // Remove port if present
    size_t port_pos = host.find(":");
    if (port_pos != std::string::npos) {
        std::string port_str = host.substr(port_pos + 1);
        port = std::stoi(port_str);
        host = host.substr(0, port_pos);
    }

    #ifdef _WIN32
        WSADATA wsaData;
        WSAStartup(MAKEWORD(2, 2), &wsaData);
    #endif

    SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == INVALID_SOCKET) return -1;

    struct hostent* server = gethostbyname(host.c_str());
    if (!server) {
        #ifdef _WIN32
            closesocket(sock);
            WSACleanup();
        #else
            close(sock);
        #endif
        return -1;
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    memcpy(&serv_addr.sin_addr.s_addr, server->h_addr, server->h_length);

    // Connect with timeout
    #ifdef _WIN32
        u_long mode = 1;
        ioctlsocket(sock, FIONBIO, &mode);
    #else
        int flags = fcntl(sock, F_GETFL, 0);
        fcntl(sock, F_SETFL, flags | O_NONBLOCK);
    #endif

    connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr));

    fd_set fdset;
    FD_ZERO(&fdset);
    FD_SET(sock, &fdset);
    struct timeval tv = {5, 0}; // 5 second timeout

    if (select(sock + 1, NULL, &fdset, NULL, &tv) == 1) {
        #ifdef _WIN32
            int so_error;
            int len = sizeof(so_error);
            getsockopt(sock, SOL_SOCKET, SO_ERROR, (char*)&so_error, &len);
            if (so_error != 0) {
                closesocket(sock);
                WSACleanup();
                return -1;
            }
        #endif
    }

    #ifdef _WIN32
        mode = 0;
        ioctlsocket(sock, FIONBIO, &mode);
    #else
        fcntl(sock, F_SETFL, flags);
    #endif

    // Build HTTP request
    std::ostringstream request;
    request << "POST " << path << " HTTP/1.1\r\n";
    request << "Host: " << host << "\r\n";
    request << "Content-Type: application/json\r\n";
    request << "Content-Length: " << jsonPayload.size() << "\r\n";
    request << "User-Agent: PC-Check-Client/1.0\r\n";
    request << "Connection: close\r\n";
    request << "\r\n";
    request << jsonPayload;

    // Send request
    int sent = send(sock, request.str().c_str(), request.str().size(), 0);

    #ifdef _WIN32
        closesocket(sock);
        WSACleanup();
    #else
        close(sock);
    #endif

    return (sent == (int)request.str().size()) ? 0 : -1;
}

std::string escapeJson(const std::string& s) {
    std::ostringstream o;
    for (char c : s) {
        switch (c) {
            case '"': o << "\\\""; break;
            case '\\': o << "\\\\"; break;
            case '\n': o << "\\n"; break;
            case '\r': o << "\\r"; break;
            case '\t': o << "\\t"; break;
            default: o << c;
        }
    }
    return o.str();
}

// ======================== MAIN ========================

int main(int argc, char* argv[]) {
    std::cout << "========================================\n";
    std::cout << "        PC VERIFICATION CHECK\n";
    std::cout << "========================================\n\n";

    // Parse command line arguments
    if (argc > 1) {
        CHECK_ID = argv[1];
    }
    if (argc > 2) {
        USER_ID = argv[2];
    }
    if (argc > 3) {
        WEBHOOK_URL = argv[3];
    }

    if (CHECK_ID.empty()) {
        std::cout << "Usage: pc_check.exe <CHECK_ID> <USER_ID> [WEBHOOK_URL]\n";
        std::cout << "  CHECK_ID: The ID provided by the staff request\n";
        std::cout << "  USER_ID: Your Discord user ID\n";
        std::cout << "  WEBHOOK_URL: (Optional) Custom webhook URL\n\n";
        std::cout << "Press Enter to exit...";
        std::cin.get();
        return 1;
    }

    if (WEBHOOK_URL == "YOUR_WEBHOOK_URL_HERE") {
        std::cout << "ERROR: Webhook URL not configured!\n";
        std::cout << "Please ask staff for the correct tool or URL.\n";
        std::cout << "Press Enter to exit...";
        std::cin.get();
        return 1;
    }

    std::cout << "Gathering system information...\n\n";

    // Collect system info
    std::string hostname = getHostname();
    std::string username = getUsername();
    std::string os_version = getOSVersion();
    std::string cpu = getCPUName();
    std::string gpu = getGPUName();
    std::string ram = getRAMInfo();
    std::string mac_address = getMACAddress();
    std::string public_ip = getPublicIP();
    std::string timestamp = getCurrentTimestamp();
    bool is_vm = isVirtualMachine();
    std::vector<std::string> suspicious = checkSuspiciousProcesses();
    std::vector<std::string> usb_devices = getUSBDevices();

    // Display info
    std::cout << "System Information Collected:\n";
    std::cout << "----------------------------------------\n";
    std::cout << "  Hostname: " << hostname << "\n";
    std::cout << "  Username: " << username << "\n";
    std::cout << "  OS: " << os_version << "\n";
    std::cout << "  CPU: " << cpu << "\n";
    std::cout << "  GPU: " << gpu << "\n";
    std::cout << "  RAM: " << ram << "\n";
    std::cout << "  MAC: " << mac_address << "\n";
    std::cout << "  Public IP: " << public_ip << "\n";
    std::cout << "  Virtual Machine: " << (is_vm ? "YES" : "No") << "\n";

    if (!suspicious.empty()) {
        std::cout << "  WARNING - Suspicious processes found:\n";
        for (const auto& proc : suspicious) {
            std::cout << "    - " << proc << "\n";
        }
    }

    std::cout << "----------------------------------------\n\n";

    // Build JSON payload
    std::ostringstream json;
    json << "{";
    json << "\"check_id\": \"" << escapeJson(CHECK_ID) << "\",";
    json << "\"user_id\": \"" << escapeJson(USER_ID) << "\",";
    json << "\"hostname\": \"" << escapeJson(hostname) << "\",";
    json << "\"username\": \"" << escapeJson(username) << "\",";
    json << "\"os_version\": \"" << escapeJson(os_version) << "\",";
    json << "\"cpu\": \"" << escapeJson(cpu) << "\",";
    json << "\"gpu\": \"" << escapeJson(gpu) << "\",";
    json << "\"ram\": \"" << escapeJson(ram) << "\",";
    json << "\"mac_address\": \"" << escapeJson(mac_address) << "\",";
    json << "\"public_ip\": \"" << escapeJson(public_ip) << "\",";
    json << "\"is_virtual_machine\": " << (is_vm ? "true" : "false") << ",";
    json << "\"timestamp\": \"" << escapeJson(timestamp) << "\",";

    // Add suspicious processes
    json << "\"suspicious_processes\": [";
    bool first = true;
    for (const auto& proc : suspicious) {
        if (!first) json << ",";
        json << "\"" << escapeJson(proc) << "\"";
        first = false;
    }
    json << "],";

    // Add USB devices
    json << "\"usb_devices\": [";
    first = true;
    for (const auto& device : usb_devices) {
        if (!first) json << ",";
        json << "\"" << escapeJson(device) << "\"";
        first = false;
    }
    json << "],";

    json << "\"status\": \"PENDING\"";
    json << "}";

    std::cout << "Sending verification to Discord...\n";

    // Send to webhook
    int result = sendWebhook(WEBHOOK_URL, json.str());

    if (result == 0) {
        std::cout << "\n========================================\n";
        std::cout << "  SUCCESS! Verification data sent.\n";
        std::cout << "========================================\n";
        std::cout << "\nYour information has been submitted for review.\n";
        std::cout << "Staff will review your check shortly.\n";
    } else {
        std::cout << "\n========================================\n";
        std::cout << "  ERROR: Failed to send verification.\n";
        std::cout << "========================================\n";
        std::cout << "\nPlease check your internet connection and try again.\n";
        std::cout << "If the problem persists, contact staff.\n";
    }

    std::cout << "\nPress Enter to exit...";
    std::cin.get();

    return result;
}
