"""中文化映射层。

数据来源固定为 data/curation/ 下五个 CSV，不另建第二套翻译系统：

- nutrient_zh.csv     营养素中文名、单位、分组、显示小数位
- category_zh.csv     分类中文名（FDC / WWEIA / 品牌分类）
- food_zh.csv         人工核验的中文食品名（status=verified / review_status=verified，按 FDC ID）
- fullname_zh.csv     完整英文描述 → 中文名精确映射（status=verified / glossary）
- glossary_rules.csv  词典规则候选（status=glossary / review_status=pending）

解析优先级（从高到低）：

1. FDC ID 专属映射（food_zh.csv）→ verified
2. 完整英文描述精确映射（fullname_zh.csv）→ verified 或 glossary（按 status 列）
3. 词典规则（glossary_rules.csv）→ glossary，但须通过多项质量门禁：
   - survey_fndds_food（膳食调查组合食品）跳过 glossary
   - 描述含明显组合食品关键词（salad, sandwich, burger, taco, burrito, omelet,
     pizza, pasta, stew, pot pie, entree, meal, snack bar）跳过
   - 描述含品牌名黑名单（APPLEBEE, KRAFT, QUAKER, MALT-O-MEAL, CHOBANI, DENNY'S,
     ON THE BORDER, REDUCED FAT, FAT FREE, NO SUGAR, NO ADDED SUGAR, WITHOUT SALT,
     REDUCED SODIUM）跳过（避免品牌名/否定词被当作食材翻译）
   - glossary 命中词 >= 4 个时放弃（说明是复杂组合，规则会拼成乱码）
   - glossary 仅命中 1 个宽泛大类词（bean→豆类, milk→牛奶, cheese→奶酪,
     beef→牛肉, pork→猪肉, chicken→鸡肉, potato→马铃薯, rice→米, bread→面包）
     时放弃（大量重名且无区分度）
4. 以上都不命中 → zh_status=none

三级状态：verified / glossary / none。品牌商品（data_type=branded_food）一律保留原文。
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT

CURATION_DIR = PROJECT_ROOT / "data" / "curation"

VERIFIED = "verified"
GLOSSARY = "glossary"
NONE = "none"

REVIEW_VERIFIED = "verified"
REVIEW_PENDING = "pending"

BRANDED_DATA_TYPE = "branded_food"
SURVEY_FNDDS = "survey_fndds_food"

# --------------------------------------------------------------------- 黑名单常量

# 组合食品关键词（出现其中之一且非单一食材时，跳过 glossary）
COMPOSITE_FOOD_KEYWORDS = re.compile(
    r"\b(salad|sandwich|burger|taco|burrito|omelet|pizza|pasta|ravioli|dumpling|"
    r"sushi|stew|pot\s*pie|entree|meal|snack\s*bar|casserole|chili|soup|wrap|"
    r"popcorn|chips|fries|doughnut|donut|cookie|brownie|cake|pie|tart|"
    r"muffin|biscuit|pancake|waffle|french\s*toast|"
    r"ice\s*cream|frozen\s*novelties|pudding|gelatin|smoothie)\b",
    re.IGNORECASE,
)

# 品牌名 / 否定词 / 非食材词黑名单（出现其中之一即跳过 glossary）
BLACKLIST_TERMS = re.compile(
    r"applebee|red\s*lobster|on\s*the\s*border|denny|ihop|kfc|mcdonald|"
    r"kelly|kraft|heinz|malt-o-meal|quaker|chobani|yoplait|general\s*mills|"
    r"cheez\s*whiz|cream\s*cheese\s*spread|cheese\s*sauce|"
    r"(?<!\w)brand(?!\w)|(?<!\w)brand\s*name|"
    r"fast\s*food|restaurant|"
    r"fat\s*free|no\s*fat|reduced\s*fat|low\s*fat|"
    r"no\s*sugar|no\s*added\s*sugar|sugar\s*free|"
    r"no\s*salt|without\s*salt|reduced\s*sodium|low\s*sodium|"
    r"no\s*gluten|gluten\s*free|"
    r"nonfat|fat\-free|"
    r"ready\-to\-eat|ready\s*to\s*eat|instant|"
    r"powder|powdered|mix|dip|spread|sauce|dressing|syrup|topping|"
    r"flavored|artificial|sweetener|preservative|"
    r"(?<!\w)ns\b|(?<!\w)nfs\b|(?<!\w)ns\s+as\s+to|"
    r"frozen\s*entree|frozen\s*dinner|microwaved|unprepared|prepared\s*from\s*package|"
    r"reduced\s*calorie|low\s*calorie|calorie\-free|"
    r"babyfood|baby\s*food|formula",
    re.IGNORECASE,
)

# 宽泛大类词（单独命中 1 个时放弃 glossary，避免大量无区分度重名）
# 只包含那些在 USDA 数据里确实导致大量不同食品被翻成同一个中文名的词：
# - bean/beans → 54 条
# - cheese → 52 条
# - beef → 38 条
# - pork → 29 条
# - chicken → 26 条
# - potato → 18 条
# - rice → 18 条
# - flour → 16 条
# - corn → 16 条
# - bread → 14 条
# - 等
BROAD_CATEGORY_TERMS = frozenset(
    {
        "bean",
        "beans",
        "milk",
        "cheese",
        "beef",
        "pork",
        "chicken",
        "turkey",
        "lamb",
        "potato",
        "rice",
        "bread",
        "flour",
        "pasta",
        "oat",
        "corn",
        "sugar",
        "salt",
        "pepper",
        "butter",
        "cream",
        "yogurt",
        "egg",
        "ice",
        "honey",
    }
)


@dataclass(frozen=True)
class NutrientZh:
    nutrient_id: int
    nbr: str
    name_en: str
    name_zh: str
    unit_zh: str
    group_zh: str
    decimals: int
    is_core: int


@dataclass(frozen=True)
class FoodZhEntry:
    fdc_id: int
    name_zh: str
    aliases: tuple[str, ...]
    pinyin: str
    category_zh: str | None


@dataclass(frozen=True)
class FullnameZhEntry:
    description_en: str
    name_zh: str
    status: str  # verified / glossary
    aliases: tuple[str, ...]
    note: str = ""


@dataclass
class ResolvedName:
    name_zh: str | None
    status: str
    review_status: str
    aliases: tuple[str, ...] = ()
    pinyin: str = ""
    reason: str = ""


@dataclass
class GlossaryRule:
    pattern: re.Pattern[str]
    name_zh: str
    raw: str


@dataclass
class ZhOverlay:
    curation_dir: Path = CURATION_DIR
    nutrients: dict[int, NutrientZh] = field(default_factory=dict)
    categories: dict[tuple[str, str], str] = field(default_factory=dict)
    foods: dict[int, FoodZhEntry] = field(default_factory=dict)
    fullnames: dict[str, FullnameZhEntry] = field(default_factory=dict)
    rules: list[GlossaryRule] = field(default_factory=list)
    loaded: bool = False

    def load(self) -> ZhOverlay:
        self.nutrients = {}
        self.categories = {}
        self.foods = {}
        self.fullnames = {}
        self.rules = []
        for row in read_curation_csv(self.curation_dir / "nutrient_zh.csv"):
            nid = int(row["nutrient_id"])
            self.nutrients[nid] = NutrientZh(
                nutrient_id=nid,
                nbr=(row.get("nbr") or "").strip(),
                name_en=(row.get("name_en") or "").strip(),
                name_zh=(row.get("name_zh") or "").strip(),
                unit_zh=(row.get("unit_zh") or "").strip(),
                group_zh=(row.get("group_zh") or "").strip(),
                decimals=int(row["decimals"]),
                is_core=int(row["is_core"]),
            )
        for row in read_curation_csv(self.curation_dir / "category_zh.csv"):
            source = (row.get("category_source") or "").strip()
            code = (row.get("category_code") or "").strip()
            name_zh = (row.get("name_zh") or "").strip()
            if source and code and name_zh:
                self.categories[(source, code)] = name_zh
        for row in read_curation_csv(self.curation_dir / "food_zh.csv"):
            fdc_id = int(row["fdc_id"])
            aliases = tuple(a for a in (row.get("aliases") or "").split(";") if a.strip())
            self.foods[fdc_id] = FoodZhEntry(
                fdc_id=fdc_id,
                name_zh=(row.get("name_zh") or "").strip(),
                aliases=aliases,
                pinyin=(row.get("pinyin") or "").strip(),
                category_zh=(row.get("category_zh") or "").strip() or None,
            )
        # fullname_zh.csv 是新增的可选层，文件不存在时跳过。
        fullname_path = self.curation_dir / "fullname_zh.csv"
        if fullname_path.exists():
            for row in read_curation_csv(fullname_path):
                desc = (row.get("description_en") or "").strip()
                name_zh = (row.get("name_zh") or "").strip()
                if not desc or not name_zh:
                    continue
                aliases = tuple(a for a in (row.get("aliases") or "").split(";") if a.strip())
                status = (row.get("status") or "glossary").strip().lower()
                if status not in (VERIFIED, GLOSSARY):
                    status = GLOSSARY
                self.fullnames[desc.lower()] = FullnameZhEntry(
                    description_en=desc,
                    name_zh=name_zh,
                    status=status,
                    aliases=aliases,
                    note=(row.get("note") or "").strip(),
                )
        for row in read_curation_csv(self.curation_dir / "glossary_rules.csv"):
            raw = (row.get("match_pattern") or "").strip()
            name_zh = (row.get("name_zh") or "").strip()
            if not raw or not name_zh:
                continue
            try:
                pattern = re.compile(raw)
            except re.error:
                continue
            self.rules.append(GlossaryRule(pattern=pattern, name_zh=name_zh, raw=raw))
        # 长词优先，避免 "milk" 抢先匹配 "almond milk" 之类的部分覆盖。
        self.rules.sort(key=lambda r: len(r.raw), reverse=True)
        self.loaded = True
        return self

    # ------------------------------------------------------------------ 分类
    def category_name(self, category_source: str | None, category_code: str | None,
                      category_en: str | None) -> str | None:
        """按（来源，编码）取中文分类名；品牌分类以英文名作为编码。"""
        if category_source and category_code:
            name = self.categories.get((category_source, category_code))
            if name:
                return name
        if category_source == "branded":
            return self.categories.get(("branded", category_en or "__blank__"))
        return None

    # ------------------------------------------------------------------ 食品名
    def resolve(self, fdc_id: int, description_en: str, data_type: str) -> ResolvedName:
        """返回中文名与状态；不编造任何未核验译名。

        优先级：FDC ID 专属 → 完整英文描述精确匹配 → glossary 规则（需过质量门禁） → none。
        """
        # 1. FDC ID 专属
        entry = self.foods.get(fdc_id)
        if entry is not None:
            return ResolvedName(
                name_zh=entry.name_zh,
                status=VERIFIED,
                review_status=REVIEW_VERIFIED,
                aliases=entry.aliases,
                pinyin=entry.pinyin,
                reason="人工核验映射（food_zh.csv，按 FDC ID）",
            )

        # 2. 品牌商品一律不翻译
        if data_type == BRANDED_DATA_TYPE:
            return ResolvedName(
                name_zh=None,
                status=NONE,
                review_status=REVIEW_PENDING,
                reason="品牌商品名称保留原文，不做机器翻译",
            )

        # 3. 完整英文描述精确匹配
        fullname_hit = self.fullnames.get(description_en.lower())
        if fullname_hit is not None:
            status = fullname_hit.status
            return ResolvedName(
                name_zh=fullname_hit.name_zh,
                status=status,
                review_status=REVIEW_VERIFIED if status == VERIFIED else REVIEW_PENDING,
                aliases=fullname_hit.aliases,
                reason=f"完整英文名精确匹配（status={status}）",
            )

        # 4. glossary 规则（需过质量门禁）
        if _should_skip_glossary(description_en, data_type):
            return ResolvedName(
                name_zh=None,
                status=NONE,
                review_status=REVIEW_PENDING,
                reason="glossary 质量门禁未通过（组合食品 / 品牌名 / 宽泛词等）",
            )

        hits = self._glossary_hits(description_en)
        if hits:
            name_zh = "".join(hits)
            # 门禁：只有一个命中，且该命中的英文原词属于宽泛大类 → 放弃。
            # 用 description_en.lower() 检查是否只包含一个 BROAD_CATEGORY_TERMS 里的词。
            if len(hits) == 1 and self._only_broad_term_hit(description_en):
                return ResolvedName(
                    name_zh=None,
                    status=NONE,
                    review_status=REVIEW_PENDING,
                    reason=f"glossary 仅命中一个宽泛大类词（{hits[0]!r}），无区分度",
                )
            # 门禁：拼接结果过长（>= 8 个中文字，基本是乱拼）→ 放弃
            if len(name_zh) >= 8:
                return ResolvedName(
                    name_zh=None,
                    status=NONE,
                    review_status=REVIEW_PENDING,
                    reason=f"glossary 拼接结果过长（{len(name_zh)} 字），疑似乱拼",
                )
            return ResolvedName(
                name_zh=name_zh,
                status=GLOSSARY,
                review_status=REVIEW_PENDING,
                reason="词典规则候选，待人工核验",
            )

        return ResolvedName(
            name_zh=None,
            status=NONE,
            review_status=REVIEW_PENDING,
            reason="无可靠中文名称，显示英文原文",
        )

    def _glossary_hits(self, description_en: str) -> list[str]:
        """词典命中 → 中文词列表，按原描述位置排序，同一中文词只出现一次。

        去重逻辑：如果连续两次命中同一个中文翻译（常见于 "milk, 3.25% milkfat"
        这种英文里同一个词出现多次），保留第一次。
        """
        found: list[tuple[int, str]] = []
        consumed: list[tuple[int, int]] = []
        for rule in self.rules:
            for match in rule.pattern.finditer(description_en):
                start, end = match.span()
                if start == end:
                    continue
                if any(s < end and start < e for s, e in consumed):
                    continue
                consumed.append((start, end))
                found.append((start, rule.name_zh))
        found.sort(key=lambda item: item[0])
        # 去重：相邻相同 name_zh 只保留第一个
        deduped: list[str] = []
        last: str | None = None
        for _, zh in found:
            if zh == last:
                continue
            deduped.append(zh)
            last = zh
        return deduped

    def _only_broad_term_hit(self, description_en: str) -> bool:
        """描述里只有 BROAD_CATEGORY_TERMS 里的英文词命中，没有其他更具体的食材词。

        用法：resolve 已确认 len(hits) == 1，这时调用本函数判断那个唯一的命中是不是
        一个宽泛大类词——如果是，说明这条食品的中文名就只剩一个宽泛词，放弃 glossary。
        """
        lower = description_en.lower()
        found_broad: set[str] = set()
        for term in BROAD_CATEGORY_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", lower):
                found_broad.add(term)
        if not found_broad:
            return False  # 没命中任何宽泛词，那唯一命中应该是具体食材名（broccoli 之类）
        # 宽泛词命中的同时，描述里还有没有其他 glossary 规则覆盖的具体食材？
        for rule in self.rules:
            rule_raw_lower = rule.raw.lower()
            if any(b in rule_raw_lower for b in found_broad):
                continue  # 这条规则本身就是宽泛词的翻译，跳过
            if rule.pattern.search(description_en):
                return False  # 有更具体的食材词也命中了，保留 glossary
        return True

    # ------------------------------------------------------------------ 搜索词
    def build_search_tokens(self, name_zh: str | None, aliases: tuple[str, ...],
                            pinyin: str, description_en: str) -> str:
        tokens: list[str] = []
        seen: set[str] = set()

        def add(token: str) -> None:
            token = token.strip().lower()
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)

        for text in (name_zh, *aliases):
            if not text:
                continue
            add(text)
            for size in (2, 3):
                for i in range(0, max(len(text) - size + 1, 0)):
                    add(text[i:i + size])
        if pinyin:
            syllables = [s for s in pinyin.split() if s]
            add("".join(syllables))
            add("".join(s[0] for s in syllables if s))
            for syllable in syllables:
                add(syllable)
        for word in re.split(r"[^0-9a-zA-Z]+", description_en.lower()):
            if len(word) >= 2:
                add(word)
        return " ".join(tokens)


def _should_skip_glossary(description_en: str, data_type: str) -> bool:
    """决定这条食品是否应该跳过 glossary 规则。

    跳过条件（任一满足即跳过）：

    1. survey_fndds_food —— 膳食调查记录本身就是组合菜，glossary 只会拼乱码。
    2. 描述里出现品牌名 / 否定词 / 非食材词（APPLEBEE, FAT FREE, NO SUGAR, ns as to...）。
    3. 描述里出现明显组合食品关键词且不是单一基础食材（salad, sandwich, pizza...）。
    """
    if data_type == SURVEY_FNDDS:
        return True

    desc = description_en or ""

    if BLACKLIST_TERMS.search(desc):
        return True

    if COMPOSITE_FOOD_KEYWORDS.search(desc):
        # 额外判定：如果除了组合关键词之外还有 >= 3 个不同食材词，基本就是组合菜
        return True

    return False


def read_curation_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"缺少中文化映射文件：{path}。请先运行 data/build/_gen_curation.py 生成 data/curation/*.csv。"
        )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
