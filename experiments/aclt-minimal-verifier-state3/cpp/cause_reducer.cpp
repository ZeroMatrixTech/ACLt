// SPDX-License-Identifier: Apache-2.0
// Narrow conformance oracle for the three published assumption causes only.
#include <iostream>
#include <set>
#include <string>
int main(int argc, char** argv) {
    std::set<std::string> seen;
    for (int i=1;i<argc;++i) {
        std::string code=argv[i];
        if ((code!="REVOKED" && code!="OUT_OF_SCOPE" && code!="WINDOW_EXPIRED") || !seen.insert(code).second) return 1;
    }
    for (const auto* code : {"REVOKED","OUT_OF_SCOPE","WINDOW_EXPIRED"}) {
        if (seen.count(code)) {std::cout << code << '\n';return 0;}
    }
    std::cout << "VALID\n";
}
