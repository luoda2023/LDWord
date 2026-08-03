from __future__ import annotations

from src.assistant.domain.exam_authoring_contract import (
    exam_generation_prompt_addendum,
    exam_request_clarification,
    generated_exam_blockers,
    generated_exam_warnings,
    parse_exam_authoring_requirements,
    resolve_exam_blueprint,
)
from src.shared.engine.exam_question_schema import parse_exam_markdown_source


def test_exam_markdown_heading_emphasis_is_normalized_before_word_rendering():
    result = parse_exam_markdown_source(
        """# ***Emphasized Exam***
## *I. Emphasized Section*
1. Plain question.（1 分）
## 答案速查
1. Plain answer.
"""
    )

    assert result.payload["paper_title"] == "Emphasized Exam"
    assert result.payload["sections"][0]["title"] == "I. Emphasized Section"


def test_exam_blueprints_distinguish_quiz_standard_and_term_scales():
    quiz = resolve_exam_blueprint("生成一份随堂测验")
    standard = resolve_exam_blueprint("生成一份高一信息技术 Python 基础试卷")
    term = resolve_exam_blueprint("生成一份高一期末试卷")

    assert (quiz.profile.profile_id, quiz.scene_id, quiz.question_count) == (
        "quiz",
        "exam_quiz",
        8,
    )
    assert quiz.profile.min_student_pages == 2
    assert (standard.profile.profile_id, standard.scene_id) == (
        "standard",
        "exam",
    )
    assert standard.question_count == 18
    assert [
        (section.question_count, section.total_score)
        for section in standard.section_blueprints
    ] == [(10, 30.0), (5, 30.0), (3, 40.0)]
    assert (
        standard.profile.min_student_pages,
        standard.profile.max_student_pages,
    ) == (4, 8)
    assert (term.profile.profile_id, term.scene_id, term.question_count) == (
        "term",
        "exam_term",
        24,
    )


def test_term_blueprint_uses_exact_integer_question_scores_without_decimal_averages():
    intent = "生成一份小学六年级英语期中考试试卷"
    blueprint = resolve_exam_blueprint(intent, scene_id="exam_term")

    plans = [section.question_score_plan() for section in blueprint.section_blueprints]

    assert plans[0] == (2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 3.0)
    assert all(
        float(score).is_integer()
        for plan in plans
        for score in plan
    )
    assert [sum(plan) for plan in plans] == [
        section.total_score for section in blueprint.section_blueprints
    ]
    assert sum(sum(plan) for plan in plans) == blueprint.total_score == 100

    prompt = exam_generation_prompt_addendum(intent, scene_id="exam_term")
    assert "禁止用小数均分" in prompt
    assert "各题依次 2、2、2、2、2、2、3、3、3、3 分" in prompt


def test_low_score_term_request_still_assigns_at_least_one_integer_point_per_question():
    blueprint = resolve_exam_blueprint(
        "生成一份期中考试试卷，共 24 道题，满分 24 分",
        scene_id="exam_term",
    )

    assert blueprint.question_count == 24
    assert blueprint.total_score == 24
    assert sum(
        section.total_score for section in blueprint.section_blueprints
    ) == 24
    assert all(
        score >= 1 and float(score).is_integer()
        for section in blueprint.section_blueprints
        for score in section.question_score_plan()
    )


def test_explicit_short_requirements_override_a_selected_term_scene():
    blueprint = resolve_exam_blueprint(
        "生成试卷，考试时间 20 分钟，满分 20 分，共 5 道题",
        scene_id="exam_term",
    )

    assert blueprint.profile.profile_id == "quiz"
    assert blueprint.scene_id == "exam_quiz"
    assert blueprint.duration_minutes == 20
    assert blueprint.total_score == 20
    assert blueprint.question_count == 5
    assert dict(blueprint.difficulty_counts) == {
        "basic": 2,
        "medium": 2,
        "advanced": 1,
    }


def test_authoritative_scale_profile_survives_a_user_defined_scene_id():
    blueprint = resolve_exam_blueprint(
        "生成一份高一信息技术试卷",
        scene_id="my_school_exam",
        scale_profile_id="term",
    )
    prompt = exam_generation_prompt_addendum(
        "生成一份高一信息技术试卷",
        scene_id="my_school_exam",
        scale_profile_id="term",
    )

    assert blueprint.profile.profile_id == "term"
    assert blueprint.question_count == 24
    assert blueprint.profile.min_student_pages == 6
    assert blueprint.profile.max_student_pages == 10
    assert "期中/期末试卷" in prompt
    assert "学生卷渲染目标为 6-10 页" in prompt


def test_type_counts_form_an_exact_user_owned_question_total():
    blueprint = resolve_exam_blueprint(
        "生成测验：单项选择题 2 道、程序阅读题 2 道、解答题 1 道"
    )

    assert blueprint.question_count == 5
    assert blueprint.question_count_source == "user_type_counts"


def test_resolved_total_keeps_default_sections_without_claiming_type_ownership():
    resolved_default = resolve_exam_blueprint(
        "生成高一信息技术单元测试试卷，共 18 道题，满分 100 分"
    )
    custom_total = resolve_exam_blueprint(
        "生成高一信息技术单元测试试卷，共 17 道题，满分 100 分"
    )

    assert resolved_default.question_count_source == "user_total"
    assert [
        section.question_count for section in resolved_default.section_blueprints
    ] == [10, 5, 3]
    assert custom_total.section_blueprints == ()


def test_exam_prompt_addendum_exposes_the_resolved_scale_contract():
    prompt = exam_generation_prompt_addendum(
        "生成一份高一信息技术 Python 基础单元测试",
        scene_id="exam",
    )

    assert "完整单元/阶段试卷" in prompt
    assert "全卷题量必须为：18 道" in prompt
    assert "学生卷渲染目标为 4-8 页" in prompt
    assert "大题蓝图必须严格为" in prompt
    assert "difficulty: 基础|中等|提高" in prompt
    assert "knowledge_points:" in prompt
    assert "两个 input() 返回的字符串可以进行字典序比较" in prompt


def test_exam_make_request_keeps_subject_grade_and_term_constraints():
    intent = "我需要制作一份初中六年级语文期中考试试卷"
    prompt = exam_generation_prompt_addendum(
        intent,
        scene_id="exam_term",
    )
    requirements = parse_exam_authoring_requirements(intent)
    clarification = exam_request_clarification(intent)

    assert "学科必须为：语文" in prompt
    assert "年级必须为：六年级" in prompt
    assert "学段必须按“初中”理解" in prompt
    assert "考试类型必须为：期中考试" in prompt
    assert "本次考试规格为“期中/期末试卷”" in prompt
    assert "全卷题量必须为：24 道" in prompt
    assert requirements.school_stage == "初中"
    assert requirements.exam_period == "期中考试"
    assert clarification is not None
    assert [option["id"] for option in clarification["options"]] == [
        "primary_grade",
        "middle_preparatory",
    ]


def test_exam_stage_clarification_answer_overrides_the_ambiguous_original_phrase():
    primary = parse_exam_authoring_requirements(
        "我需要制作一份初中六年级语文期中考试试卷\n补充确认：小学六年级"
    )
    preparatory = parse_exam_authoring_requirements(
        "我需要制作一份初中六年级语文期中考试试卷\n补充确认：初中预备班（六年级）"
    )

    assert (primary.school_stage, primary.grade) == ("小学", "六年级")
    assert (preparatory.school_stage, preparatory.grade) == ("初中", "六年级")


def test_exam_grade_and_subject_comparison_accepts_school_stage_prefixes():
    markdown = """# 小学六年级英语期中试卷
> 科目：小学英语　年级：小学六年级　考试时间：90 分钟　满分：100 分
## 一、选择题
1. Choose A.（100 分）
   A. A
   B. B
   difficulty: 基础
   knowledge_points: vocabulary
## 答案速查
1. A
"""
    result = parse_exam_markdown_source(markdown)
    blockers = generated_exam_blockers(
        markdown,
        result,
        intent="帮我生成一份小学六年级的期中英语考试试卷",
        scene_id="exam_term",
        scale_profile_id="term",
    )

    assert "requested_grade_mismatch" not in blockers
    assert "requested_subject_mismatch" not in blockers


def test_grade_comparison_preserves_middle_and_high_school_semantics():
    cases = (
        ("生成一份初中一年级数学期中试卷", "初一"),
        ("生成一份高中一年级数学期中试卷", "高一"),
    )
    for intent, actual_grade in cases:
        markdown = f"""# {actual_grade}数学期中试卷
> 科目：数学　年级：{actual_grade}　考试时间：90 分钟　满分：100 分
## 一、选择题
1. 1 + 1 = ?（100 分）
   A. 1
   B. 2
   difficulty: 基础
   knowledge_points: 加法
## 答案速查
1. B
"""
        result = parse_exam_markdown_source(markdown)
        blockers = generated_exam_blockers(
            markdown,
            result,
            intent=intent,
            scene_id="exam_term",
        )

        assert "requested_grade_mismatch" not in blockers
        assert exam_request_clarification(intent) is None


def test_shared_language_instruction_is_not_treated_as_a_duplicate_question():
    markdown = """# 六年级英语随堂测验
> 科目：英语　年级：六年级　考试时间：20 分钟　满分：20 分
## 一、选择题
1. Choose the correct answer.（10 分）
   A. apple
   B. orange
   difficulty: 基础
   knowledge_points: fruit
2. Choose the correct answer.（10 分）
   A. Monday
   B. Friday
   difficulty: 基础
   knowledge_points: weekday
## 答案速查
1. A
2. B
"""
    result = parse_exam_markdown_source(markdown)
    blockers = generated_exam_blockers(
        markdown,
        result,
        intent="生成六年级英语随堂测验，共 2 道题，满分 20 分，考试时间 20 分钟",
        scene_id="exam_quiz",
    )

    assert "duplicate_question_stem" not in blockers


def test_knowledge_point_coverage_is_a_warning_not_a_hard_blocker():
    markdown = """# 六年级英语随堂测验
> 科目：英语　年级：六年级　考试时间：20 分钟　满分：20 分
## 一、选择题
1. Question one?（10 分）
   A. A
   B. B
   difficulty: 基础
   knowledge_points: vocabulary
2. Question two?（10 分）
   A. A
   B. B
   difficulty: 基础
   knowledge_points: vocabulary
## 答案速查
1. A
2. B
"""
    result = parse_exam_markdown_source(markdown)
    kwargs = {
        "intent": "生成六年级英语随堂测验，共 2 道题，满分 20 分，考试时间 20 分钟",
        "scene_id": "exam_quiz",
    }

    assert "knowledge_point_coverage_too_low" not in generated_exam_blockers(
        markdown,
        result,
        **kwargs,
    )
    assert "knowledge_point_coverage_too_low" in generated_exam_warnings(
        markdown,
        result,
        **kwargs,
    )


def test_generated_exam_quality_contract_accepts_complete_quiz_metadata():
    markdown = """# 高一信息技术 Python 基础随堂测验
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：20 分

## 一、单项选择题
1. input() 的返回值类型是什么？（4 分）
   A. int
   B. str
   C. list
   D. bool
   difficulty: 基础
   knowledge_points: 输入输出、数据类型
2. range(3) 依次产生哪组值？（4 分）
   A. 0, 1, 2
   B. 1, 2, 3
   C. 0, 1, 2, 3
   D. 3
   difficulty: 基础
   knowledge_points: for 循环、range

## 二、程序阅读题
3. 阅读程序 `x = int(input()); print(x + 1)`，输入 4 时输出什么？（4 分）
   difficulty: 中等
   knowledge_points: 类型转换、表达式
   answer_area_kind: lines
   answer_lines: 1
4. 阅读程序 `a = []; a.append(2); print(len(a))`，写出输出。（4 分）
   difficulty: 中等
   knowledge_points: 列表、len
   answer_area_kind: lines
   answer_lines: 1

## 三、解答题
5. 编写函数判断一个整数是否为偶数，并返回判断结果。（4 分）
   difficulty: 提高
   knowledge_points: 函数、条件分支、取余运算
   answer_area_kind: free
   answer_lines: 4

## 答案速查
1. B
2. A
3. 5
4. 1
5. 示例：`def is_even(n): return n % 2 == 0`
"""
    result = parse_exam_markdown_source(markdown)
    blockers = generated_exam_blockers(
        markdown,
        result,
        intent=(
            "生成一份高一信息技术试卷，考试时间 20 分钟，满分 20 分，"
            "共 5 道题：单项选择题 2 道、程序阅读题 2 道、解答题 1 道"
        ),
        scene_id="exam_quiz",
    )

    assert result.error_count == 0
    assert blockers == ()

    period_blockers = generated_exam_blockers(
        markdown,
        result,
        intent=(
            "生成一份高一信息技术期末考试试卷，考试时间 20 分钟，满分 20 分，"
            "共 5 道题：单项选择题 2 道、程序阅读题 2 道、解答题 1 道"
        ),
        scene_id="exam_quiz",
    )
    assert "requested_exam_period_mismatch" in period_blockers


def test_generated_exam_quality_contract_warns_on_missing_difficulty_metadata():
    markdown = """# 测验
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：5 分

## 一、简答题
1. 说明变量的作用。（5 分）
   knowledge_points: 变量

## 答案速查
1. 用于保存程序运行中的数据。
"""
    result = parse_exam_markdown_source(markdown)
    blockers = generated_exam_blockers(
        markdown,
        result,
        intent="生成随堂测验，考试时间 20 分钟，满分 5 分，共 1 道题",
        scene_id="exam_quiz",
    )
    warnings = generated_exam_warnings(
        markdown,
        result,
        intent="生成随堂测验，考试时间 20 分钟，满分 5 分，共 1 道题",
        scene_id="exam_quiz",
    )

    assert "difficulty_metadata_incomplete" not in blockers
    assert "difficulty_metadata_incomplete" in warnings


def test_renderable_exam_incompleteness_is_reviewable_instead_of_blocking():
    markdown = """# 六年级语文测验
> 科目：语文　年级：六年级　考试时间：20 分钟　满分：10 分
## 一、填空题
1. 第一题。（5 分）
   difficulty: 基础
   knowledge_points: 识记
2. 第二题。
   difficulty: 中等
   knowledge_points: 理解
## 答案速查
1. 示例答案
"""
    result = parse_exam_markdown_source(markdown)
    kwargs = {
        "intent": "生成六年级语文测验，共 2 道题，满分 10 分，考试时间 20 分钟",
        "scene_id": "exam_quiz",
    }

    blockers = generated_exam_blockers(markdown, result, **kwargs)
    warnings = generated_exam_warnings(markdown, result, **kwargs)

    assert "answer_coverage_incomplete" not in blockers
    assert "score_coverage_incomplete" not in blockers
    assert "answer_coverage_incomplete" in warnings
    assert "score_coverage_incomplete" in warnings


def test_indented_numbered_requirements_remain_inside_one_question_stem():
    markdown = """# 编程题
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：10 分

## 一、程序设计题
1. 编写一个完整程序，完成以下要求。（10 分）
    1. 输入一个整数。
    2. 判断它是否为偶数。
    3. 输出判断结果。
   difficulty: 提高
   knowledge_points: 输入输出、条件分支

## 答案速查
1. 示例答案略。
"""

    result = parse_exam_markdown_source(markdown)

    assert result.error_count == 0
    assert result.summary.question_count == 1
    question = result.payload["sections"][0]["questions"][0]
    assert "1. 输入一个整数" in question["stem"]
    assert "3. 输出判断结果" in question["stem"]


def test_choice_options_accept_label_then_multiline_code_block():
    markdown = """# 代码选择题
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：5 分

## 一、单项选择题
1. 哪段代码会输出 3？（5 分）
   A.
   ```python
   print(1 + 2)
   ```
   B.
   ```python
   print(1 * 2)
   ```
   difficulty: 基础
   knowledge_points: 表达式

## 答案速查
1. A
"""

    result = parse_exam_markdown_source(markdown)
    question = result.payload["sections"][0]["questions"][0]

    assert result.error_count == 0
    assert question["options"] == [
        "A.\nprint(1 + 2)",
        "B.\nprint(1 * 2)",
    ]


def test_question_lead_in_before_number_is_attached_to_the_following_question():
    markdown = """# 程序阅读题
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：10 分

## 一、基础题
1. input() 返回什么类型？（4 分）
   A. int
   B. str
   difficulty: 基础
   knowledge_points: input、数据类型

## 二、程序阅读题
**程序片段一：**
```python
n = int(input())
print(n + 1)
```
2. 输入 7 时，程序输出什么？（6 分）
   difficulty: 提高
   knowledge_points: 类型转换、表达式
   answer_area_kind: lines
   answer_lines: 1

## 答案速查
**一、基础题**
1. **B**。解析：input() 返回字符串。
---
**二、程序阅读题**
2. **参考答案**：8。解析：7 加 1 等于 8。
"""

    result = parse_exam_markdown_source(markdown)
    first = result.payload["sections"][0]["questions"][0]
    second = result.payload["sections"][1]["questions"][0]

    assert result.error_count == 0
    assert "程序片段" not in first["stem"]
    assert second["lead_in"] == (
        "程序片段一：\n"
        "n = int(input())\n"
        "print(n + 1)"
    )
    assert first["answer"] == "B"
    assert second["answer"] == "8"
    assert "**" not in first["analysis"]
    assert "二、程序阅读题" not in first["analysis"]


def test_generated_exam_quality_contract_rejects_false_python_string_comparison_error():
    markdown = """# Python 测验
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：10 分

## 一、程序阅读题
1. 阅读程序并判断：a 和 b 均由 input() 直接取得；执行 `if a > b:` 时，
   系统会因字符串不支持 `>` 比较而报错。请说明原因。（10 分）
   difficulty: 提高
   knowledge_points: input、字符串比较
   answer_area_kind: lines
   answer_lines: 2

## 答案速查
1. input() 返回字符串。
"""
    # Keep executable-looking assignments in the same parsed question.
    markdown = markdown.replace(
        "阅读程序并判断：",
        "阅读程序并判断：\n   a = input()\n   b = input()\n",
    )
    result = parse_exam_markdown_source(markdown)
    blockers = generated_exam_blockers(
        markdown,
        result,
        intent="生成高一信息技术测验，考试时间 20 分钟，满分 10 分，共 1 道题",
        scene_id="exam_quiz",
    )

    assert "python_string_comparison_error_claim" in blockers


def test_subquestion_scores_sum_to_the_declared_whole_question_score():
    markdown = """# 程序分析题
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：6 分

## 一、程序阅读题（本大题共 1 小题，每小题 6 分，共 6 分）
1. 阅读程序并回答：
   （1）写出运行结果。（4 分）
   （2）说明判断条件的作用。（2 分）
   difficulty: 提高
   knowledge_points: 程序追踪、条件判断
   answer_area_kind: lines
   answer_lines: 3

## 答案速查
1. 结果与说明略。
"""

    result = parse_exam_markdown_source(markdown)
    question = result.payload["sections"][0]["questions"][0]

    assert result.error_count == 0
    assert question["score"] == "6"
    assert "（1）写出运行结果。（4 分）" in question["stem"]
    assert "（2）说明判断条件的作用。（2 分）" in question["stem"]


def test_python_string_to_integer_comparison_requires_type_error_answer():
    question_block = """# Python 类型比较测验
> 科目：信息技术　年级：高一　考试时间：20 分钟　满分：10 分

## 一、单项选择题
1. 阅读程序并选择运行结果：（10 分）
   n = input()
   m = 10
   print(n > m)
   A. False
   B. True
   C. 9
   D. 程序运行时出现异常
   difficulty: 基础
   knowledge_points: input、类型比较

## 答案速查
"""
    bad_markdown = question_block + (
        "1. B。解析：字符串的 ASCII 码值通常大于整数，因此逻辑值为 True。\n"
    )
    good_markdown = question_block + (
        "1. D。解析：input() 返回字符串，字符串与整数使用 > 比较会抛出 TypeError。\n"
    )
    intent = "生成高一信息技术测验，考试时间 20 分钟，满分 10 分，共 1 道题"

    bad_result = parse_exam_markdown_source(bad_markdown)
    bad_blockers = generated_exam_blockers(
        bad_markdown,
        bad_result,
        intent=intent,
        scene_id="exam_quiz",
    )
    good_result = parse_exam_markdown_source(good_markdown)
    good_blockers = generated_exam_blockers(
        good_markdown,
        good_result,
        intent=intent,
        scene_id="exam_quiz",
    )

    assert "python_mixed_type_comparison_answer_incorrect" in bad_blockers
    assert "python_mixed_type_comparison_answer_incorrect" not in good_blockers
