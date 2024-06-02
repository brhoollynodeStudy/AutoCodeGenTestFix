import os
import sys
import subprocess
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAI

# 设置 OpenAI API 密钥
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-api-key')  # 这里替换为你的 OpenAI API 密钥
llm = OpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-4o")

# 定义 CodeGenerationAgent，用于生成初始代码
code_generation_template = PromptTemplate(
    input_variables=["requirement"],
    template="根据以下需求生成 Python 代码，只返回代码部分，不包含任何说明或解释：\n\n需求：{requirement}\n\n代码："
)
code_generation_chain = code_generation_template | llm

# 定义 TestGenerationAgent，用于生成测试用例
test_generation_template = PromptTemplate(
    input_variables=["code"],
    template="根据以下代码生成 Python 的单元测试用例，只返回测试代码，不包含任何说明或解释：\n\n{code}\n\n测试代码："
)
test_generation_chain = test_generation_template | llm

# 定义 TestExecutionAgent，用于执行测试用例
class TestExecutionAgent:
    def run(self, params):
        project_name = params['project_name']
        test_command = f"cd {project_name} && pytest"
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True)
        return result.stdout

# 定义 TestResultAgent，用于获取测试结果
class TestResultAgent:
    def run(self, params):
        test_output = params['test_output']
        if "FAILURES" in test_output or "FAILED" in test_output:
            return "测试失败"
        else:
            return "测试通过"

# 定义 CodeFixAgent，用于修复代码
code_fix_template = PromptTemplate(
    input_variables=["code", "test_output"],
    template="以下是有问题的代码和测试输出结果，请基于这些信息修复代码，只返回修复后的代码，不包含任何说明或解释：\n\n代码：{code}\n\n测试输出：{test_output}\n\n修复后的代码："
)
code_fix_chain = code_fix_template | llm

def extract_code_from_response(response):
    code_lines = response.splitlines()
    code = "\n".join(line for line in code_lines if line.strip() and not line.strip().startswith("#"))
    return code

def run_app(requirement, project_name, max_retries=3):
    os.makedirs(project_name, exist_ok=True)

    try:
        raw_code = code_generation_chain.invoke({"requirement": requirement})
        code = extract_code_from_response(raw_code)
        code_file_path = os.path.join(project_name, "example_function.py")
        with open(code_file_path, "w") as file:
            file.write(code)
    except Exception as e:
        print(f"生成初始代码失败: {e}")
        return

    try:
        raw_test_code = test_generation_chain.invoke({"code": code})
        test_code = extract_code_from_response(raw_test_code)
        test_file_path = os.path.join(project_name, "test_example_function.py")
        with open(test_file_path, "w") as file:
            file.write(test_code)
    except Exception as e:
        print(f"生成测试用例失败: {e}")
        return

    test_execution_agent = TestExecutionAgent()
    test_result_agent = TestResultAgent()

    for attempt in range(max_retries):
        try:
            test_output = test_execution_agent.run({"project_name": project_name})
            print(test_output)
        except Exception as e:
            print(f"执行测试用例失败: {e}")
            return

        try:
            test_result = test_result_agent.run({"test_output": test_output})
            print(test_result)
        except Exception as e:
            print(f"获取测试结果失败: {e}")
            return

        if test_result == "测试通过":
            break

        try:
            raw_code = code_fix_chain.run({"code": code, "test_output": test_output})
            code = extract_code_from_response(raw_code)
            with open(code_file_path, "w") as file:
                file.write(code)
        except Exception as e:
            print(f"修复代码失败: {e}")
            return

    try:
        with open(code_file_path, "r") as file:
            final_code = file.read()
        return final_code
    except Exception as e:
        print(f"读取最终代码失败: {e}")
        return

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供需求描述")
        sys.exit(1)

    requirement = sys.argv[1]
    project_name = "generated_project"
    final_code = run_app(requirement, project_name)

    if final_code:
        print("最终实现的代码：")
        print(final_code)