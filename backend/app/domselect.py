"""轻量 DOM 解析与选择器匹配：供抽取预演在页面快照 DOM 上核对锚点命中。

只依赖标准库 html.parser，覆盖预演所需的子集：
- CSS：标签、*、#id、.class、[attr]、[attr="值"]、后代/子代组合、逗号分组
- XPath：//tag、/tag、*、[@attr='值']、[contains(@class,'值')]
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser


class Node:
    """DOM 节点：标签、属性、按文档顺序排列的子节点/文本。"""

    __slots__ = ("tag", "attrs", "items", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Node | None" = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.items: list[Node | str] = []
        self.parent = parent

    @property
    def children(self) -> list["Node"]:
        return [item for item in self.items if isinstance(item, Node)]

    def text(self) -> str:
        parts: list[str] = []
        for item in self.items:
            parts.append(item if isinstance(item, str) else item.text())
        return "".join(parts)


_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "source", "track", "wbr",
}


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].items.append(node)
        if node.tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].items.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag:
                del self.stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].items.append(data.strip())


def parse_dom(html_text: str) -> Node:
    """把 HTML 文本解析成节点树，根节点标签为 document。"""
    builder = _TreeBuilder()
    builder.feed(html_text)
    builder.close()
    return builder.root


def node_path(node: Node) -> str:
    """生成 XPath 风格的节点路径，如 /html/body/div[2]/span[1]。"""
    parts: list[str] = []
    current: Node | None = node
    while current is not None and current.tag != "document":
        index = 1
        if current.parent is not None:
            siblings = [c for c in current.parent.children if c.tag == current.tag]
            index = siblings.index(current) + 1
        parts.append(f"{current.tag}[{index}]")
        current = current.parent
    return "/" + "/".join(reversed(parts))


def outer_html(node: Node, max_len: int = 240) -> str:
    """重建节点的外层 HTML 作为 DOM 片段，超长截断。"""
    attrs = "".join(f' {k}="{escape(v, quote=True)}"' for k, v in node.attrs.items())
    inner = "".join(
        item if isinstance(item, str) else outer_html(item, max_len)
        for item in node.items
    )
    fragment = f"<{node.tag}{attrs}>{inner}</{node.tag}>"
    if len(fragment) > max_len:
        return fragment[: max_len - 1] + "…"
    return fragment


def _walk(node: Node) -> list[Node]:
    out = [node]
    for child in node.children:
        out.extend(_walk(child))
    return out


# ---------------- CSS 子集 ----------------

_COMPOUND_RE = re.compile(
    r"(?P<attr>\[[^\]]+\])|(?P<id>\#[\w-]+)|(?P<class>\.[\w-]+)|(?P<tag>\*|[a-zA-Z][\w-]*)"
)
_ATTR_RE = re.compile(r"^([\w-]+)\s*(?:=\s*(['\"]?)(.*?)\2)?$")


def _parse_compound(token: str) -> dict:
    spec: dict = {"tag": None, "id": None, "classes": [], "attrs": []}
    pos = 0
    for match in _COMPOUND_RE.finditer(token):
        if match.start() != pos:
            raise ValueError(f"无法解析的选择器片段：{token}")
        pos = match.end()
        if match.group("attr"):
            inner = match.group("attr")[1:-1].strip()
            attr_match = _ATTR_RE.match(inner)
            if not attr_match:
                raise ValueError(f"无法解析的属性选择器：[{inner}]")
            spec["attrs"].append((attr_match.group(1).lower(), attr_match.group(3)))
        elif match.group("id"):
            spec["id"] = match.group("id")[1:]
        elif match.group("class"):
            spec["classes"].append(match.group("class")[1:])
        elif match.group("tag"):
            tag = match.group("tag")
            spec["tag"] = None if tag == "*" else tag.lower()
    if pos != len(token):
        raise ValueError(f"无法解析的选择器片段：{token}")
    return spec


def _tokenize(branch: str) -> list[tuple[str, str]]:
    """把一个选择器分支拆成 [(组合子, 复合选择器)]，首个组合子为 ''。"""
    steps: list[tuple[str, str]] = []
    buf = ""
    combinator = ""
    depth = 0
    for ch in branch.strip():
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if depth == 0 and ch == ">":
            if buf.strip():
                steps.append((combinator, buf.strip()))
                buf = ""
            combinator = ">"
            continue
        if depth == 0 and ch.isspace():
            if buf.strip():
                steps.append((combinator, buf.strip()))
                buf = ""
                combinator = " "
            continue
        buf += ch
    if buf.strip():
        steps.append((combinator, buf.strip()))
    return steps


def _matches_compound(node: Node, spec: dict) -> bool:
    if spec["tag"] and node.tag != spec["tag"]:
        return False
    if spec["id"] and node.attrs.get("id") != spec["id"]:
        return False
    node_classes = node.attrs.get("class", "").split()
    if any(cls not in node_classes for cls in spec["classes"]):
        return False
    for name, value in spec["attrs"]:
        if name not in node.attrs:
            return False
        if value is not None and node.attrs.get(name) != value:
            return False
    return True


def _match_steps(node: Node, steps: list[tuple[str, dict]], idx: int) -> bool:
    if not _matches_compound(node, steps[idx][1]):
        return False
    if idx == 0:
        return True
    combinator = steps[idx][0]
    parent = node.parent
    if combinator == ">":
        return (
            parent is not None
            and parent.tag != "document"
            and _match_steps(parent, steps, idx - 1)
        )
    while parent is not None and parent.tag != "document":
        if _match_steps(parent, steps, idx - 1):
            return True
        parent = parent.parent
    return False


def css_select(root: Node, selector: str) -> list[Node]:
    """按文档顺序返回命中的节点，逗号分组的结果去重后拼接。"""
    matched: list[Node] = []
    for branch in selector.split(","):
        steps = [(comb, _parse_compound(token)) for comb, token in _tokenize(branch)]
        if not steps:
            continue
        last = len(steps) - 1
        for node in _walk(root):
            if node.tag == "document":
                continue
            if _match_steps(node, steps, last) and node not in matched:
                matched.append(node)
    return matched


# ---------------- XPath 子集 ----------------

_XPATH_STEP_RE = re.compile(r"^(?P<test>\*|[a-zA-Z][\w-]*)(?:\[(?P<pred>[^\]]+)\])?$")
_PRED_CONTAINS_RE = re.compile(r"^contains\(\s*@([\w-]+)\s*,\s*['\"]([^'\"]*)['\"]\s*\)$")
_PRED_ATTR_RE = re.compile(r"^@([\w-]+)\s*=\s*['\"]([^'\"]*)['\"]$")


def _xpath_steps(expr: str) -> list[tuple[str, str, str | None]]:
    steps: list[tuple[str, str, str | None]] = []
    i, n = 0, len(expr.strip())
    expr = expr.strip()
    while i < n:
        if expr.startswith("//", i):
            axis, i = "desc", i + 2
        elif expr[i] == "/":
            axis, i = "child", i + 1
        else:
            raise ValueError(f"不支持的 XPath 表达式：{expr}")
        j = i
        depth = 0
        while j < n:
            ch = expr[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            elif ch == "/" and depth == 0:
                break
            j += 1
        body = expr[i:j]
        match = _XPATH_STEP_RE.match(body)
        if not match:
            raise ValueError(f"不支持的 XPath 步骤：{body}")
        test = match.group("test")
        steps.append((axis, "*" if test == "*" else test.lower(), match.group("pred")))
        i = j
    if not steps:
        raise ValueError(f"不支持的 XPath 表达式：{expr}")
    return steps


def _xpath_predicate(node: Node, pred: str) -> bool:
    pred = pred.strip()
    contains = _PRED_CONTAINS_RE.match(pred)
    if contains:
        return contains.group(2) in node.attrs.get(contains.group(1).lower(), "")
    attr = _PRED_ATTR_RE.match(pred)
    if attr:
        return node.attrs.get(attr.group(1).lower()) == attr.group(2)
    raise ValueError(f"不支持的 XPath 谓词：[{pred}]")


def xpath_select(root: Node, expr: str) -> list[Node]:
    current = [root]
    for axis, test, pred in _xpath_steps(expr):
        nxt: list[Node] = []
        for node in current:
            candidates = _walk(node)[1:] if axis == "desc" else node.children
            for candidate in candidates:
                if test != "*" and candidate.tag != test:
                    continue
                if pred and not _xpath_predicate(candidate, pred):
                    continue
                if candidate not in nxt:
                    nxt.append(candidate)
        current = nxt
    return current
