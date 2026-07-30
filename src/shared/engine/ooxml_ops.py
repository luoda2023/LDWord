"""
ooxml_ops — Open XML 常用操作封装

对 python-docx 底层 lxml 元素的常见操作封装。
"""

from __future__ import annotations

from copy import deepcopy
from lxml import etree

# Word Open XML 命名空间
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

NSMAP = {
    "w": W_NS,
    "r": R_NS,
    "m": M_NS,
}


def qn(tag: str) -> str:
    """快速限定名, e.g. qn('w:pPr') → '{http://...}pPr'"""
    prefix, local = tag.split(":", 1) if ":" in tag else ("w", tag)
    ns = NSMAP.get(prefix, W_NS)
    return f"{{{ns}}}{local}"


def find(element, tag: str):
    """查找子元素。"""
    return element.find(qn(tag))


def find_all(element, tag: str) -> list:
    """查找所有匹配子元素。"""
    return element.findall(qn(tag))


def find_or_create(parent, tag: str):
    """查找子元素，不存在则创建。"""
    child = parent.find(qn(tag))
    if child is None:
        child = etree.SubElement(parent, qn(tag))
    return child


def get_val(element, tag: str) -> str | None:
    """获取子元素的 w:val 属性值。"""
    child = element.find(qn(tag))
    if child is not None:
        return child.get(qn("w:val"))
    return None


def set_val(parent, tag: str, value: str) -> None:
    """设置子元素的 w:val 属性值（不存在则创建）。"""
    child = find_or_create(parent, tag)
    child.set(qn("w:val"), value)


def remove_element(element) -> None:
    """从父节点中移除元素。"""
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def remove_child(parent, tag: str) -> bool:
    """移除指定 tag 的子元素。"""
    child = parent.find(qn(tag))
    if child is not None:
        parent.remove(child)
        return True
    return False


def clone_element(element):
    """深拷贝 XML 元素。"""
    return deepcopy(element)


def set_attribute(element, attr: str, value: str) -> None:
    """设置元素属性（自动加命名空间前缀）。"""
    if ":" in attr:
        element.set(qn(attr), value)
    else:
        element.set(attr, value)


def set_inline_shape_alt_text(
    inline_shape,
    *,
    alt_text: str,
    title: str = "",
) -> None:
    """Set accessible description metadata on a python-docx inline shape."""

    doc_pr = getattr(getattr(inline_shape, "_inline", None), "docPr", None)
    if doc_pr is None:
        return
    doc_pr.set("descr", alt_text)
    if title:
        doc_pr.set("title", title)


def get_attribute(element, attr: str) -> str | None:
    """获取元素属性。"""
    if ":" in attr:
        return element.get(qn(attr))
    return element.get(attr)


def create_element(tag: str, **attrs) -> etree._Element:
    """创建元素, e.g. create_element('w:sz', **{'w:val': '24'})"""
    elem = etree.Element(qn(tag))
    for k, v in attrs.items():
        elem.set(qn(k) if ":" in k else k, str(v))
    return elem


def element_to_string(element, pretty: bool = False) -> str:
    """元素→XML字符串（调试用）。"""
    return etree.tostring(
        element, pretty_print=pretty, encoding="unicode"
    )
