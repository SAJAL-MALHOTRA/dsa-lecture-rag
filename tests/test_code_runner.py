"""
Unit tests for the safe code runner.
"""

from ytrag.code_runner import execute_code


def test_execute_python_success():
    code = """
def two_sum(a, b):
    return a + b

print("Result:", two_sum(10, 25))
"""
    res = execute_code("python", code)
    assert res["success"] is True
    assert "Result: 35" in res["stdout"]
    assert res["exit_code"] == 0
    assert res["execution_time_ms"] > 0


def test_execute_python_syntax_error():
    code = "def broken(:"
    res = execute_code("python", code)
    assert res["success"] is False
    assert "SyntaxError" in res["stderr"]
    assert res["exit_code"] != 0


def test_execute_python_timeout():
    code = """
import time
while True:
    time.sleep(0.1)
"""
    res = execute_code("python", code, timeout_sec=1.0)
    assert res["success"] is False
    assert "Time Limit Exceeded" in res["stderr"]


def test_execute_cpp_success():
    code = """
int main() {
    cout << "C++ 20 Runner Works: " << (100 / 4) << endl;
    return 0;
}
"""
    res = execute_code("cpp", code)
    assert res["success"] is True
    assert "C++ 20 Runner Works: 25" in res["stdout"]
    assert res["exit_code"] == 0


def test_execute_cpp_compile_error():
    code = """
int main() {
    this_is_invalid_syntax_error();
    return 0;
}
"""
    res = execute_code("cpp", code)
    assert res["success"] is False
    assert "error" in res["stderr"].lower()


def test_execute_unsupported_language():
    res = execute_code("ruby", "puts 'hello'")
    assert res["success"] is False
    assert "Unsupported" in res["stderr"]


def test_python_security_blocks_dangerous_modules():
    bad_code = "import os\nos.system('echo hi')"
    res = execute_code("python", bad_code)
    assert res["success"] is False
    assert "Security Sandbox Violation" in res["stderr"]
    assert "os" in res["stderr"]


def test_python_security_blocks_eval_exec():
    bad_code = "eval('1 + 1')"
    res = execute_code("python", bad_code)
    assert res["success"] is False
    assert "Security Sandbox Violation" in res["stderr"]
    assert "eval" in res["stderr"]


def test_python_security_blocks_subclasses_jailbreak():
    bad_code = "classes = ().__class__.__base__.__subclasses__()"
    res = execute_code("python", bad_code)
    assert res["success"] is False
    assert "Security Sandbox Violation" in res["stderr"]


def test_cpp_security_blocks_system_call():
    bad_code = """
int main() {
    system("shutdown /s");
    return 0;
}
"""
    res = execute_code("cpp", bad_code)
    assert res["success"] is False
    assert "Security Sandbox Violation" in res["stderr"]
    assert "system()" in res["stderr"]


def test_cpp_security_blocks_forbidden_header():
    bad_code = """
#include <windows.h>
int main() {
    return 0;
}
"""
    res = execute_code("cpp", bad_code)
    assert res["success"] is False
    assert "Security Sandbox Violation" in res["stderr"]
    assert "windows.h" in res["stderr"]

