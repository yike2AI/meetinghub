# 官网设计规范指南

> 本文档用于指导 AI 生成与 官网风格一致的页面设计

---

## 1. 品牌色彩系统

### 主色调
| 颜色名称 | 色值 | 用途 |
|---------|------|------|
| 品牌蓝 | `#165DFF` | 主按钮、链接、高亮 |
| 品牌深蓝 | `#044AE9` | hover状态、渐变终点 |
| 渐变蓝 | `linear-gradient(135deg, #165DFF 0%, #044AE9 100%)` | 主按钮、激活标签 |

### 辅助色
| 颜色名称 | 色值 | 用途 |
|---------|------|------|
| 强调橙 | `#FF6B6B` / `#FF8E53` | Hot标签、强调元素 |
| 成功绿 | `#10B981` / `#34D399` | 成功状态、正向提示 |
| 功能紫 | `#8B5CF6` / `#A78BFA` | 特色功能卡片 |
| 活力青 | `#00C9A7` / `#00E5B8` | 产品生态图标 |

### 中性色
| 颜色名称 | 色值 | 用途 |
|---------|------|------|
| 主文字 | `#151515` | 标题、正文 |
| 次要文字 | `#6C6F7D` | 描述、辅助文字 |
| 边框色 | `#E8ECFF` | 卡片边框、分割线 |
| 背景灰 | `#F8FAFF` / `#F0F5FF` | 页面背景、hover背景 |
| 白色 | `#FFFFFF` | 卡片背景、内容区 |

---

## 2. 字体规范

### 字体栈
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
```

### 字号层级
| 元素 | 字号 | 字重 | 行高 |
|-----|------|------|------|
| H1主标题 | 48-56px | 500-700 | 140% |
| H2副标题 | 24-32px | 600-700 | 140% |
| H3小标题 | 18-20px | 600 | 140% |
| 正文 | 14-16px | 400-500 | 140% |
| 辅助文字 | 12-13px | 400 | 140% |
| 标签/徽章 | 10-11px | 600 | 140% |

---

## 3. 圆角规范

| 元素 | 圆角值 |
|-----|--------|
| 大卡片/模块 | `16px` / `rounded-[16px]` |
| 按钮 | `6px` / `rounded-[6px]` |
| 输入框 | `12px` / `rounded-[12px]` |
| 小标签/徽章 | `full` / `rounded-full` |
| 下拉菜单 | `12px` / `rounded-[12px]` |
| 图标容器 | `7-8px` / `rounded-[7px]` |

---

## 4. 阴影规范

### 卡片阴影
```css
/* 默认卡片 */
box-shadow: 0 4px 16px rgba(22, 93, 255, 0.08);

/* Hover状态 */
box-shadow: 0 12px 32px rgba(22, 93, 255, 0.15);

/* 下拉菜单 */
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
```

### 按钮阴影
```css
/* 渐变按钮Hover */
box-shadow: 0 4px 12px rgba(22, 93, 255, 0.3);
```

---

## 5. 动画与过渡

### 过渡函数
```css
/* 标准过渡 */
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

/* 快速过渡 */
transition: all 0.2s ease-out;

/* 按钮颜色过渡 */
transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
```

### 常用动画
```css
/* 卡片Hover上浮 */
transform: translateY(-4px);

/* 选项Hover右移 */
transform: translateX(4px);

/* 特色选项 */
transform: translateX(4px) scale(1.02);
```

---

## 6. 组件规范

### 主按钮
```html
<button class="bg-[#165DFF] hover:bg-[#044AE9] text-white rounded-[6px] font-medium transition-colors duration-200">
  按钮文字
</button>
```

### 渐变按钮
```html
<button class="bg-gradient-to-r from-[#165DFF] to-[#044AE9] hover:shadow-[0_4px_12px_rgba(22,93,255,0.3)] text-white rounded-[6px] font-medium transition-all duration-200">
  按钮文字
</button>
```

### 卡片
```html
<div class="bg-white rounded-[16px] border border-[#E8ECFF] overflow-hidden card-hover">
  <!-- 卡片内容 -->
</div>
```

### 标签
```html
<!-- 默认标签 -->
<span class="px-5 py-2 rounded-full text-[14px] font-medium bg-white text-[#6C6F7D] border border-[#E8ECFF] hover:border-[#165DFF] hover:text-[#165DFF] transition-all">
  标签文字
</span>

<!-- 激活标签 -->
<span class="px-5 py-2 rounded-full text-[14px] font-medium text-white bg-gradient-to-r from-[#165DFF] to-[#044AE9]">
  激活标签
</span>
```

### 下拉菜单
```html
<div class="relative trial-trigger">
  <button>触发按钮</button>
  <div class="trial-dropdown">
    <div class="bg-white rounded-[12px] shadow-[0_8px_24px_rgba(0,0,0,0.12)] p-3 min-w-[240px] backdrop-blur-sm border border-[#E8ECFF]">
      <!-- 下拉内容 -->
    </div>
  </div>
</div>
```

---

## 7. 布局规范

### 容器宽度
| 场景 | 宽度 |
|-----|------|
| 主内容区 | `1200px` / `w-[1200px]` |
| 移动端 | 100% + padding |

### 间距规范
| 场景 | 值 |
|-----|-----|
| 模块间距 | 80-120px |
| 卡片内边距 | 24-32px |
| 元素间距 | 16-24px |
| 紧凑间距 | 8-12px |

---

## 8. Header 导航结构

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] 首页  产品生态▼  私有化部署  产品动态  更新日志  [免费体验▼] │
└─────────────────────────────────────────────────────────────┘
```

### 导航链接样式
```html
<a class="text-[#151515] hover:text-[#165DFF] transition-colors duration-200 font-medium">
  导航文字
</a>
```

### 当前页高亮
```html
<a class="text-[#165DFF] font-medium">
  当前页面
</a>
```

---

## 9. 自定义弹窗规范

### 提示弹窗结构
```html
<!-- 遮罩层 -->
<div class="custom-toast-overlay"></div>

<!-- 弹窗 -->
<div class="custom-toast">
  <div class="custom-toast-icon">
    <!-- SVG图标 -->
  </div>
  <div class="custom-toast-title">提示</div>
  <div class="custom-toast-message">消息内容</div>
  <button class="custom-toast-btn">我知道了</button>
</div>
```

### 弹窗样式
```css
.custom-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0.9);
  background: white;
  border-radius: 16px;
  padding: 32px 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: center;
  min-width: 280px;
}

.custom-toast.show {
  opacity: 1;
  visibility: visible;
  transform: translate(-50%, -50%) scale(1);
}

.custom-toast-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  z-index: 9998;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s ease;
}
```

---

## 10. 图标规范

### 图标尺寸
| 场景 | 尺寸 |
|-----|------|
| 导航图标 | 16-20px |
| 卡片图标 | 40-56px |
| 按钮图标 | 16-20px |
| 功能图标 | 24-28px |

### 图标风格
- 使用 Stroke 风格（描边）
- 线宽：1.5-2px
- 圆角线帽
- 统一使用 `currentColor` 继承文字颜色

### SVG示例
```html
<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M..."/>
</svg>
```

---

## 11. SEO 规范

### 基础 Meta
```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>页面标题 | JitWord - 副标题描述</title>
<meta name="description" content="页面描述，150字以内">
<meta name="keywords" content="关键词,逗号分隔">
```

### Open Graph
```html
<meta property="og:title" content="页面标题">
<meta property="og:description" content="页面描述">
<meta property="og:type" content="website">
<meta property="og:url" content="https://jitword.com/page.html">
<meta property="og:image" content="https://jitword.com/assets/logo.png">
```

---

## 12. 素材资源

### 背景图
- `screen-1-bg.webp` - 首页首屏背景
- `screen-3-bg.webp` - 功能展示背景
- `screen-5-bg.webp` - 底部CTA背景

### 装饰元素
- `screen1 element 1/2/3.svg` - 首屏装饰元素
- `screen 2 icon 1-8.svg` - 功能图标集

### Logo
- `logo.png` - 品牌Logo

---

## 13. 常用类名速查

| 类名 | 用途 |
|-----|------|
| `text-gradient` | 渐变文字效果 |
| `card-hover` | 卡片Hover动效 |
| `tag-active` | 激活状态标签 |
| `trial-dropdown` | 下拉菜单容器 |
| `trial-option` | 下拉选项 |
| `trial-badge` | Hot/新上线徽章 |
| `line-clamp-2/3` | 文字截断 |

---

## 14. 设计原则

1. **简洁现代** - 留白充足，信息层级清晰
2. **品牌一致** - 蓝色主调贯穿全站
3. **微交互丰富** - Hover、过渡动画细腻
4. **响应式优先** - 移动端体验一致
5. **组件复用** - 保持组件样式统一

---

*文档版本: 1.0*
*更新日期: 2026-01-22*
