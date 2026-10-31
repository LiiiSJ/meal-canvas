import type { ReactElement, SVGProps } from 'react'

/** 统一 48×48 视框、圆头线条、扁平双色填充的自绘食材插画。 */
const INK = '#4a443c'
const CREAM = '#fff4e3'
const WHITE = '#ffffff'
const GREEN = '#8fbf8b'
const GREEN_DARK = '#638f68'
const ORANGE = '#f2a65a'
const YELLOW = '#e9c46a'
const RED = '#d97b66'
const PINK = '#f0b7a6'
const BROWN = '#b98a5e'
const SKY = '#a9cfdd'

const sp = {
  stroke: INK,
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

type IconProps = SVGProps<SVGSVGElement>
type IconComponent = (props: IconProps) => ReactElement

const rice: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M9 27h30c-1.6 8.4-7.4 13-15 13s-13.4-4.6-15-13Z" fill={WHITE} {...sp} />
    <path d="M13 27c1-4.8 5.4-7.8 11-7.8S34 22.2 35 27" fill={CREAM} {...sp} />
    <path d="M17 24.5h.01M23 22.8h.01M29 24.5h.01" {...sp} strokeWidth={2.6} />
    <path d="M14 33h20" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const noodles: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M8 26h32c-1.4 9-7.6 14-16 14S9.4 35 8 26Z" fill={WHITE} {...sp} />
    <path d="M13 26c1.6-3.2 3.6-3.2 5.2 0s3.6 3.2 5.2 0 3.6-3.2 5.2 0 3.6 3.2 5.2 0" {...sp} stroke={ORANGE} />
    <path d="M18 20 33 9M23 21 38 10" {...sp} />
  </svg>
)

const bread: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M8 21c0-5.2 4.6-8.5 16-8.5S40 15.8 40 21v11c0 3-2.2 5-5.2 5H13.2c-3 0-5.2-2-5.2-5V21Z" fill={YELLOW} {...sp} />
    <path d="M13 19c1.2-2.8 5.4-4.3 11-4.3s9.8 1.5 11 4.3" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
    <path d="m18 17-3 7M26 16l-3 8M34 17l-3 7" stroke={BROWN} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const oats: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M10 25h28c-1.2 9-7 14-14 14s-12.8-5-14-14Z" fill={WHITE} {...sp} />
    <path d="M14 25c1-3.4 4.8-5.6 10-5.6S33 21.6 34 25" fill={CREAM} {...sp} />
    <circle cx="19" cy="23" r="1.4" fill={BROWN} />
    <circle cx="24" cy="21.6" r="1.4" fill={BROWN} />
    <circle cx="29" cy="23" r="1.4" fill={BROWN} />
    <path d="M32 13c2.4 3.2 2.4 6.4 0 9.6" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const egg: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 7c7.6 0 13 9.4 13 17.6C37 33.8 31.3 40 24 40S11 33.8 11 24.6C11 16.4 16.4 7 24 7Z" fill={CREAM} {...sp} />
    <circle cx="24" cy="26" r="7" fill={ORANGE} stroke={INK} strokeWidth={2} />
    <circle cx="21.6" cy="23.6" r="1.8" fill="#fff8ee" />
  </svg>
)

const milk: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M15 17h18v21a3 3 0 0 1-3 3H18a3 3 0 0 1-3-3V17Z" fill={WHITE} {...sp} />
    <path d="m15 17 4.4-6h9.2L33 17" fill={SKY} {...sp} />
    <path d="M16 23h16v8H16z" fill={SKY} />
    <path d="M20 27.5h8" stroke={WHITE} strokeWidth={2.4} strokeLinecap="round" />
    <path d="M22 11V8h4v3" {...sp} />
  </svg>
)

const yogurt: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M13 17h22l-2.2 22a3 3 0 0 1-3 2.7h-11.6a3 3 0 0 1-3-2.7L13 17Z" fill={WHITE} {...sp} />
    <ellipse cx="24" cy="17" rx="11" ry="4.4" fill={CREAM} {...sp} />
    <path d="M24 20c3.4 0 6 2 6 4.4S27.4 29 24 29s-6-2-6-4.6S20.6 20 24 20Z" fill={PINK} />
    <path d="M30 12l6-5" {...sp} />
  </svg>
)

const cheese: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M6 32 24 12l18 20-18 7-18-7Z" fill={YELLOW} {...sp} />
    <circle cx="19" cy="28" r="2.6" fill={CREAM} />
    <circle cx="28" cy="31" r="2" fill={CREAM} />
    <circle cx="31" cy="23" r="2.4" fill={CREAM} />
    <path d="M6 32h36" stroke={BROWN} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const chicken: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M22 10c7.2-2.6 14 1.8 14 9.2 0 5-3 9.2-8 11.4-4 1.8-6 4.4-6 8.4" fill={BROWN} {...sp} />
    <path d="M22 39c3.4 0 6-2 6-5.4" {...sp} />
    <path d="M14 28c-2.2-4.2-1-9.4 3-12.2 3.6-2.6 8.6-2.2 11.6.8" stroke={INK} strokeWidth={2} fill={PINK} strokeLinecap="round" />
    <circle cx="13" cy="37" r="3" fill={WHITE} {...sp} />
    <circle cx="18" cy="40" r="3" fill={WHITE} {...sp} />
  </svg>
)

const beef: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M10 27c-2-7 2-14 9-16 6-1.8 13 1 16 6 3.6 6 1.6 14-4.4 18-5.6 3.6-14 2.8-18-2-1.6-1.8-2.2-3.8-2.6-6Z" fill={RED} {...sp} />
    <path d="M17 18c3-2 7-2 9 1M22 30c3 1 6 0 8-2M26 16c2 1 4 3 4 6" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const pork: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M13 20c0-6.6 4.6-11 11.4-11 7 0 11.6 4.4 11.6 11.6 0 5-2 9-5.4 12l-4.6 3.8V40h-6v-3.6l-3.4-3.4C13.6 30 13 25.4 13 20Z" fill={PINK} {...sp} />
    <path d="M18 21c1.6-3.6 4.6-5.4 8.4-4.8 3.4.6 5.4 3 5.4 6.2 0 3-1.4 5.4-3.8 6.8" stroke={RED} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const fish: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M9 24c5-7.4 11-11 18-11s13 3.6 18 11c-5 7.4-11 11-18 11S14 31.4 9 24Z" fill={SKY} {...sp} />
    <path d="m9 24-4-6v12l4-6Z" fill={SKY} {...sp} />
    <circle cx="33" cy="22" r="1.8" fill={INK} />
    <path d="M19 17c2 4 2 10 0 14M25 15c2 5 2 13 0 18" stroke={WHITE} strokeWidth={2.2} strokeLinecap="round" />
  </svg>
)

const shrimp: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M37 14c-9-7-24-2-26 10-1.6 10 8 17 17 13" fill={ORANGE} {...sp} />
    <path d="M39 10c2 3 2 6 1 9" {...sp} />
    <path d="M15 24c4-2 8-1 10 2s1 7-2 9" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
    <path d="M36 17c-3 2-5 5-5 9" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
    <circle cx="18" cy="22" r="1.6" fill={INK} />
  </svg>
)

const tofu: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M10 18 24 11l14 7v14L24 39l-14-7V18Z" fill={WHITE} {...sp} />
    <path d="m10 18 14 7 14-7M24 25v14" stroke={INK} strokeWidth={2} strokeLinejoin="round" />
    <path d="M13 15.5 24 10l11 5.5" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
    <circle cx="19" cy="24" r="1.6" fill={GREEN} />
    <circle cx="28" cy="31" r="1.6" fill={GREEN} />
  </svg>
)

const beans: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M9 12c8 0 24 6 30 24-8 0-24-6-30-24Z" fill={GREEN} {...sp} />
    <circle cx="16" cy="16.5" r="3" fill={GREEN_DARK} />
    <circle cx="21" cy="19.5" r="3" fill={GREEN_DARK} />
    <circle cx="26" cy="23.5" r="3" fill={GREEN_DARK} />
    <circle cx="31" cy="28.5" r="3" fill={GREEN_DARK} />
  </svg>
)

const nuts: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M17 8c5.4 0 9 5.4 9 11.4 0 7-3.6 12.2-9 12.2s-9-5.2-9-12.2C8 13.4 11.6 8 17 8Z" fill={BROWN} {...sp} />
    <path d="M17 12c2.6 2.6 3.4 6.6 2.4 11.4" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
    <path d="M33 20c4 0 6.6 4 6.6 8.4 0 5.2-2.8 9-6.6 9s-6.6-3.8-6.6-9c0-4.4 2.6-8.4 6.6-8.4Z" fill={ORANGE} {...sp} />
    <path d="M33 24c1.6 1.8 2.2 4.4 1.6 7" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const leafy: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 40V20" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
    <path d="M24 24c-7.4 0-12-4.6-12-11 7.4 0 12 4.6 12 11Z" fill={GREEN} {...sp} />
    <path d="M24 20c0-6.4 4.6-11 12-11 0 6.4-4.6 11-12 11Z" fill={GREEN} {...sp} />
    <path d="M24 32c-5.4 0-9-3.4-9-8 5.4 0 9 3.4 9 8Z" fill={GREEN_DARK} {...sp} />
    <path d="M24 30c0-4.6 3.4-8 9-8 0 4.6-3.4 8-9 8Z" fill={GREEN_DARK} {...sp} />
  </svg>
)

const broccoli: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M20 25h8v11c0 2-1.6 4-4 4s-4-2-4-4V25Z" fill={GREEN_DARK} {...sp} />
    <circle cx="16" cy="18" r="7" fill={GREEN} {...sp} />
    <circle cx="32" cy="18" r="7" fill={GREEN} {...sp} />
    <circle cx="24" cy="13" r="7.4" fill={GREEN} {...sp} />
    <path d="M18 28c1.6-2 3.6-2 6 0 2.4-2 4.4-2 6 0" stroke={WHITE} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const carrot: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M20 18c5.4 0 9.4 4 9.4 9.2 0 7.4-6 14.8-9.4 16.8-3.4-2-9.4-9.4-9.4-16.8 0-5.2 4-9.2 9.4-9.2Z" fill={ORANGE} {...sp} transform="rotate(18 20 30)" />
    <path d="M31 14c2.6 1.4 4.6 3.4 6 6M28 9c2.6.4 5 1.6 7 3.6" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
    <path d="M15 25h10M14 31h9M17 37h6" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const tomato: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <circle cx="24" cy="27" r="15" fill={RED} {...sp} />
    <path d="M24 12c-1.4-4-4-6.4-8-7 0 2.6 1 5 3 7M24 12c1.4-4 4-6.4 8-7 0 2.6-1 5-3 7" fill={GREEN} {...sp} />
    <path d="M24 12v5" stroke={GREEN_DARK} strokeWidth={2} strokeLinecap="round" />
    <path d="M16 22c1.6-2 4-3 6.4-3" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const potato: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M11 24c-1.6-8 4.6-14 13-13 8 1 13.6 6.4 13 14-.6 8-6 15-13.6 15C15.8 40 12.6 32 11 24Z" fill={BROWN} {...sp} />
    <circle cx="18" cy="22" r="1.8" fill={CREAM} />
    <circle cx="28" cy="18" r="1.6" fill={CREAM} />
    <circle cx="24" cy="30" r="1.8" fill={CREAM} />
    <circle cx="33" cy="27" r="1.4" fill={CREAM} />
  </svg>
)

const corn: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 27c-4.6 0-8-3.4-8-9 0-6 3.4-12 8-12s8 6 8 12c0 5.6-3.4 9-8 9Z" fill={YELLOW} {...sp} />
    <path d="M20 10c-5.4 1.6-8.6 6-8.6 12 0 6 3 11 8 13.4M28 10c5.4 1.6 8.6 6 8.6 12 0 6-3 11-8 13.4" fill={GREEN} {...sp} />
    <path d="M20 12h.01M24 10h.01M28 12h.01M20 18h.01M24 16h.01M28 18h.01M20 24h.01M24 22h.01M28 24h.01" stroke={BROWN} strokeWidth={2.4} strokeLinecap="round" />
  </svg>
)

const mushroom: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M8 24C8 15.2 15 9 24 9s16 6.2 16 15c0 2.4-1.6 4-4 4H12c-2.4 0-4-1.6-4-4Z" fill={BROWN} {...sp} />
    <path d="M18 28h12v9c0 3-2.4 5-6 5s-6-2-6-5v-9Z" fill={CREAM} {...sp} />
    <circle cx="16" cy="20" r="2" fill={CREAM} />
    <circle cx="26" cy="16" r="1.8" fill={CREAM} />
    <circle cx="32" cy="22" r="1.6" fill={CREAM} />
  </svg>
)

const apple: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 15c8-4 15 1 15 10 0 8-6 15-11 15-2 0-2.6-1-4-1s-2 1-4 1c-5 0-11-7-11-15 0-9 7-14 15-10Z" fill={RED} {...sp} />
    <path d="M24 15V9" stroke={BROWN} strokeWidth={2} strokeLinecap="round" />
    <path d="M24 11c3-4 7-5 10-3-1 4-5 6-10 5Z" fill={GREEN} {...sp} />
    <path d="M16 22c1-2 2.6-3 4.6-3" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const citrus: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <circle cx="24" cy="26" r="15" fill={ORANGE} {...sp} />
    <circle cx="24" cy="26" r="9" fill={YELLOW} stroke={CREAM} strokeWidth={2} />
    <path d="M24 17v18M15 26h18M17.6 19.6l12.8 12.8M30.4 19.6 17.6 32.4" stroke={CREAM} strokeWidth={1.6} strokeLinecap="round" />
    <path d="M28 10c2-3 5-4 8-2-1 3-4 5-8 4Z" fill={GREEN} {...sp} />
  </svg>
)

const berry: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 15c7 0 12 4.6 12 10.4C36 33 30.4 40 24 40s-12-7-12-14.6C12 19.6 17 15 24 15Z" fill={RED} {...sp} />
    <path d="M24 15c-2.6-3.4-6.6-4.6-10-2 1.6 3.4 5 5 10 4.4M24 15c2.6-3.4 6.6-4.6 10-2-1.6 3.4-5 5-10 4.4" fill={GREEN} {...sp} />
    <path d="M18 23h.01M24 21h.01M30 23h.01M20 30h.01M27 29h.01M24 35h.01" stroke={CREAM} strokeWidth={2.4} strokeLinecap="round" />
  </svg>
)

const banana: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M12 13c0 14 9 24 24 24 1.6 0 3-1 3-2.4 0-1.2-1-2-2.4-2-11 0-18.6-8-19-18.6 0-1.4-.8-2.4-2.6-2.4s-3 1-3 2.4Z" fill={YELLOW} {...sp} />
    <path d="M13 13c1 8 6 14 14 16" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const oil: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M20 15h8v5l4 5v15a3 3 0 0 1-3 3H19a3 3 0 0 1-3-3V25l4-5v-5Z" fill={YELLOW} {...sp} />
    <path d="M21 8h6v7h-6z" fill={BROWN} {...sp} />
    <path d="M16 28h16v8H16z" fill={CREAM} />
    <path d="M19 32h10" stroke={ORANGE} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const seasoning: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M15 18h18l-2 21a3 3 0 0 1-3 2.8H20A3 3 0 0 1 17 39l-2-21Z" fill={WHITE} {...sp} />
    <path d="M13 13h22v5H13z" fill={SKY} {...sp} />
    <circle cx="20" cy="27" r="1.2" fill={INK} />
    <circle cx="24" cy="25" r="1.2" fill={INK} />
    <circle cx="28" cy="28" r="1.2" fill={INK} />
    <circle cx="22" cy="32" r="1.2" fill={INK} />
    <circle cx="27" cy="34" r="1.2" fill={INK} />
  </svg>
)

const drink: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M13 15h22l-2.4 24a3 3 0 0 1-3 2.8H18.4a3 3 0 0 1-3-2.8L13 15Z" fill={WHITE} {...sp} />
    <path d="M14 22h20" stroke={ORANGE} strokeWidth={2} strokeLinecap="round" />
    <path d="M30 15 36 7" stroke={GREEN_DARK} strokeWidth={2.4} strokeLinecap="round" />
    <path d="M27 8h9" stroke={GREEN_DARK} strokeWidth={2.4} strokeLinecap="round" />
  </svg>
)

const packaged: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M9 15 24 8l15 7v20l-15 6-15-6V15Z" fill={ORANGE} {...sp} />
    <path d="m9 15 15 6 15-6M24 21v20" stroke={INK} strokeWidth={2} strokeLinejoin="round" />
    <path d="M14 27h6v6h-6z" fill={CREAM} />
    <path d="M28 30h6" stroke={CREAM} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

const grain: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <path d="M24 41V15" stroke={GREEN_DARK} strokeWidth={2.4} strokeLinecap="round" />
    <path d="M24 15c-5.4 0-9-3.4-9-8 5.4 0 9 3.4 9 8ZM24 15c5.4 0 9-3.4 9-8-5.4 0-9 3.4-9 8ZM24 24c-5.4 0-9-3.4-9-8 5.4 0 9 3.4 9 8ZM24 24c5.4 0 9-3.4 9-8-5.4 0-9 3.4-9 8ZM24 33c-4.6 0-7.6-2.8-7.6-6.8 4.6 0 7.6 2.8 7.6 6.8ZM24 33c4.6 0 7.6-2.8 7.6-6.8-4.6 0-7.6 2.8-7.6 6.8Z" fill={YELLOW} {...sp} />
  </svg>
)

const plate: IconComponent = (props) => (
  <svg viewBox="0 0 48 48" fill="none" {...props}>
    <circle cx="24" cy="24" r="17" fill={WHITE} {...sp} />
    <circle cx="24" cy="24" r="11" fill={CREAM} stroke={GREEN} strokeWidth={2} />
    <path d="M8 8v10M15 8v10M11.5 8v20" stroke={INK} strokeWidth={2} strokeLinecap="round" />
  </svg>
)

export const foodIconComponents = {
  rice,
  noodles,
  bread,
  oats,
  egg,
  milk,
  yogurt,
  cheese,
  chicken,
  beef,
  pork,
  fish,
  shrimp,
  tofu,
  beans,
  nuts,
  leafy,
  broccoli,
  carrot,
  tomato,
  potato,
  corn,
  mushroom,
  apple,
  citrus,
  berry,
  banana,
  oil,
  seasoning,
  drink,
  packaged,
  grain,
  plate,
} as const

/** 类别兜底复用同一套插画，不另画一套。 */
export const categoryIconComponents = {
  grain,
  dairy: milk,
  protein: chicken,
  vegetable: leafy,
  fruit: apple,
  fat: oil,
  beverage: drink,
  snack: packaged,
  other: plate,
} as const

export type FoodIconId = keyof typeof foodIconComponents
export type CategoryIconId = keyof typeof categoryIconComponents
