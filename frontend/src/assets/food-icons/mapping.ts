import type { CategoryIconId, FoodIconId } from '@/assets/food-icons/icons'

export interface FoodIconSource {
  name_zh?: string | null
  description_en?: string | null
  category_zh?: string | null
  category_en?: string | null
  category_code?: string | null
  category_source?: string | null
  data_type?: string | null
  library_scope?: string | null
  zh_status?: string | null
}

export type CategoryGroup =
  | 'grain'
  | 'protein'
  | 'dairy'
  | 'vegetable'
  | 'fruit'
  | 'fat'
  | 'beverage'
  | 'snack'
  | 'other'

type KeywordRule = readonly [FoodIconId, readonly string[]]

/**
 * 关键词按“具体食品优先”的顺序排列。
 * 英文原名参与匹配；中文名仅在已核验时参与，避免把待核验的词典译名当成事实。
 */
const KEYWORD_RULES: readonly KeywordRule[] = [
  ['egg', ['egg', 'omelet', '鸡蛋', '蛋']],
  ['milk', ['milk', '牛奶', '乳饮']],
  ['yogurt', ['yogurt', 'yoghurt', '酸奶']],
  ['cheese', ['cheese', '奶酪', '芝士']],
  ['chicken', ['chicken', 'turkey', 'poultry', '鸡', '火鸡', '禽']],
  ['beef', ['beef', 'steak', 'veal', '牛肉', '犊牛']],
  ['pork', ['pork', 'ham', 'bacon', 'sausage', 'hot dog', '猪肉', '火腿', '培根', '香肠']],
  ['fish', ['fish', 'salmon', 'tuna', 'cod', 'tilapia', '鱼', '三文鱼', '金枪鱼', '鳕鱼']],
  ['shrimp', ['shrimp', 'prawn', 'crab', 'lobster', 'oyster', 'scallop', '虾', '蟹', '龙虾', '贝']],
  ['tofu', ['tofu', 'soybean', 'soy ', '豆腐', '豆制品', '大豆']],
  ['beans', ['bean', 'lentil', 'chickpea', 'pea', '豆', '扁豆', '豌豆']],
  [
    'nuts',
    [
      'almond',
      'walnut',
      'peanut',
      'cashew',
      'pistachio',
      'pecan',
      'seed',
      '坚果',
      '花生',
      '杏仁',
      '核桃',
      '腰果',
      '籽',
    ],
  ],
  ['broccoli', ['broccoli', 'cauliflower', '西兰花', '花椰菜']],
  ['corn', ['corn', 'maize', '玉米']],
  ['mushroom', ['mushroom', '菇', '蘑菇']],
  ['carrot', ['carrot', '胡萝卜']],
  ['tomato', ['tomato', '番茄', '西红柿']],
  ['potato', ['potato', '薯', '土豆', '红薯']],
  [
    'leafy',
    [
      'spinach',
      'lettuce',
      'kale',
      'cabbage',
      'arugula',
      'celery',
      'greens',
      'eggplant',
      '菠菜',
      '生菜',
      '卷心菜',
      '甘蓝',
      '芹菜',
      '茄子',
    ],
  ],
  ['apple', ['apple', '苹果']],
  ['citrus', ['orange', 'lemon', 'lime', 'grapefruit', '柑橘', '橙', '柠檬']],
  [
    'berry',
    ['berry', 'grape', 'strawberry', 'blueberry', 'raspberry', '葡萄', '草莓', '蓝莓', '树莓'],
  ],
  ['banana', ['banana', '香蕉']],
  ['rice', ['rice', '米饭', '大米', '米']],
  ['noodles', ['noodle', 'pasta', 'spaghetti', 'macaroni', 'ramen', '面', '意面', '拉面']],
  ['bread', ['bread', 'toast', 'bagel', 'bun', 'tortilla', '面包', '吐司', '贝果']],
  ['oats', ['oat', 'cereal', 'granola', 'quinoa', '麦片', '燕麦', '藜麦']],
  [
    'packaged',
    [
      'candy',
      'chocolate',
      'cookie',
      'cake',
      'cracker',
      'chips',
      'snack',
      '零食',
      '糖果',
      '巧克力',
      '饼干',
      '蛋糕',
      '薯片',
    ],
  ],
  ['oil', ['oil', 'butter', 'margarine', '食用油', '植物油', '黄油']],
  [
    'seasoning',
    ['salt', 'sugar', 'spice', 'pepper', 'sauce', 'vinegar', 'seasoning', '盐', '糖', '香辛', '酱', '醋'],
  ],
  ['drink', ['juice', 'coffee', 'tea', 'soda', 'water', 'beverage', '饮料', '果汁', '咖啡', '茶']],
]

const FDC_CODE_FALLBACK: Record<string, CategoryGroup> = {
  '1': 'dairy',
  '2': 'snack',
  '3': 'other',
  '4': 'fat',
  '5': 'protein',
  '6': 'other',
  '7': 'protein',
  '8': 'grain',
  '9': 'fruit',
  '10': 'protein',
  '11': 'vegetable',
  '12': 'other',
  '13': 'protein',
  '14': 'beverage',
  '15': 'protein',
  '16': 'other',
  '17': 'protein',
  '18': 'grain',
  '19': 'snack',
  '20': 'grain',
  '21': 'other',
  '22': 'other',
  '23': 'snack',
  '24': 'other',
  '25': 'other',
  '26': 'other',
  '27': 'other',
  '28': 'beverage',
}

const CATEGORY_KEYWORDS: readonly [CategoryGroup, readonly string[]][] = [
  ['dairy', ['milk', 'yogurt', 'cheese', 'cream', '乳', '奶', '酸奶', '奶酪']],
  ['protein', ['meat', 'poultry', 'beef', 'pork', 'chicken', 'fish', 'seafood', 'egg', '肉', '禽', '鱼', '虾', '蛋', '贝']],
  ['vegetable', ['vegetable', '蔬菜', '菜']],
  ['fruit', ['fruit', '水果']],
  ['grain', ['grain', 'cereal', 'pasta', 'bread', '谷物', '米', '面', '面包', '早餐']],
  ['fat', ['oil', 'fat', '油脂']],
  ['beverage', ['beverage', 'drink', 'juice', 'coffee', 'tea', '饮料', '咖啡', '茶']],
  ['snack', ['snack', 'sweet', 'candy', '零食', '甜', '蛋糕', '饼干']],
]

function normalize(value: string | null | undefined): string {
  return (value ?? '').toLowerCase()
}

/** 分类兜底：只决定图标类别，不改变任何数据字段。 */
export function resolveCategoryGroup(source: FoodIconSource): CategoryGroup {
  const code = source.category_code ?? ''
  if (source.category_source === 'fdc' && /^\d{1,2}$/.test(code)) {
    return FDC_CODE_FALLBACK[code] ?? 'other'
  }

  const categoryText = `${normalize(source.category_zh)} ${normalize(source.category_en)}`
  if (categoryText.trim()) {
    for (const [group, words] of CATEGORY_KEYWORDS) {
      if (words.some((word) => categoryText.includes(word))) return group
    }
  }

  if (source.library_scope === 'branded' || source.data_type === 'branded_food') return 'snack'
  return 'other'
}

/** 同一食品在所有页面都必须得到同一个图标。 */
export function resolveFoodIcon(source: FoodIconSource): FoodIconId | CategoryIconId {
  const englishText = normalize(source.description_en)
  if (englishText) {
    for (const [icon, words] of KEYWORD_RULES) {
      if (words.some((word) => englishText.includes(word))) return icon
    }
  }

  if (source.zh_status === 'verified' || source.zh_status === 'glossary') {
    const chineseText = normalize(source.name_zh)
    if (chineseText) {
      for (const [icon, words] of KEYWORD_RULES) {
        if (words.some((word) => chineseText.includes(word))) return icon
      }
    }
  }

  const group = resolveCategoryGroup(source)
  return group
}
