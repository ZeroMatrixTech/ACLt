#include <charconv>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <thread>
#include <chrono>

long long number(const std::string& s) {
    if (s.empty() || s == "-0" || (s.size()>1 && s[0]=='0') ||
        (s.size()>2 && s[0]=='-' && s[1]=='0')) throw std::runtime_error("noncanonical integer");
    long long n;
    auto r = std::from_chars(s.data(), s.data()+s.size(), n);
    if (r.ec != std::errc() || r.ptr != s.data()+s.size()) throw std::runtime_error("invalid integer");
    return n;
}
int main(int argc, char** argv) {
    try {
        if (argc != 3 && argc != 7) throw std::runtime_error("usage: worker INPUT CHUNK_SIZE");
        auto chunk = number(argv[2]);
        if (chunk < 1 || chunk > 100000) throw std::runtime_error("chunk out of range");
        const bool single = argc == 7;
        auto selected = single ? number(argv[3]) : -1;
        auto attempt = single ? number(argv[4]) : 0;
        std::string mode = single ? argv[5] : "normal";
        auto delay = single ? number(argv[6]) : 0;
        if (single && (selected < 0 || attempt < 1 || delay < 0 || delay > 10000))
            throw std::runtime_error("invalid job arguments");
        if (mode != "normal" && mode != "slow" && mode != "wrong" && mode != "crash" &&
            mode != "hang" && mode != "duplicate" && mode != "malformed" && mode != "wrong-attempt")
            throw std::runtime_error("unknown test mode");
        if (mode == "crash") return 7;
        if (mode == "hang") { for (;;) std::this_thread::sleep_for(std::chrono::seconds(1)); }
        if (mode == "slow") std::this_thread::sleep_for(std::chrono::milliseconds(delay));
        std::ifstream f(argv[1], std::ios::binary);
        if (!f) throw std::runtime_error("cannot open input");
        f.seekg(0, std::ios::end);
        if (f.tellg() > 2000000) throw std::runtime_error("input too large");
        f.seekg(0);
        std::vector<long long> values;
        std::string token;
        while (f >> token) {
            auto n = number(token);
            if (n < -1000000000 || n > 1000000000 || values.size() >= 100000)
                throw std::runtime_error("input limit exceeded");
            values.push_back(n);
        }
        if (f.bad() || values.empty()) throw std::runtime_error("empty or unreadable input");
        if (single && static_cast<size_t>(selected) >= (values.size()+chunk-1)/chunk)
            throw std::runtime_error("block out of range");
        for (size_t start=0, id=0; start<values.size(); start+=chunk, ++id) {
            if (single && id != static_cast<size_t>(selected)) continue;
            auto end = std::min(values.size(), start+static_cast<size_t>(chunk));
            long long sum=0, lo=values[start], hi=lo;
            for(auto i=start; i<end; ++i) {sum+=values[i]; lo=std::min(lo,values[i]); hi=std::max(hi,values[i]);}
            if (mode == "wrong") ++sum;
            if (mode == "malformed") { std::cout << "bad result\n"; return 0; }
            for (int copy=0; copy < (mode == "duplicate" ? 2 : 1); ++copy) {
                if (single) std::cout << (mode == "wrong-attempt" ? attempt+1 : attempt) << ' ';
                std::cout << id << ' ' << start << ' ' << end-start << ' ' << sum << ' ' << lo << ' ' << hi << '\n';
            }
        }
        return 0;
    } catch(const std::exception& e) {std::cerr << "REJECT: " << e.what() << '\n'; return 1;}
}
