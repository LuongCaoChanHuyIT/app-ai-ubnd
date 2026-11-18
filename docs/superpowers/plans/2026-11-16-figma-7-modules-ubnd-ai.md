# Bộ Trợ Lý AI UBND Xã/Phường — 7-Module Figma Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a tested Figma Design Plugin + FigJam Workflow Diagram that renders all 7 modules (plus 1 Design System & Component frame) of **Bộ Trợ lý AI UBND xã, phường (TSH)** as 100% editable native Figma Auto-Layout frames (`1440×960` px), Variables, and Components.

**Architecture:** Author modular TypeScript builders under `src/figma-plugin/` verified offline via Node's built-in test runner (`node --test`) against a strict Mock Figma Scenegraph, then bundle them into a zero-import single-file `dist/code.ts` + PropsKit `dist/ui.html`. Publish the plugin to the user's Figma library (`planKey: "team::1703004690588386734"`) via `create_generative_plugin` / `update_generative_plugin` (bypassing Starter/View remote `use_figma` unavailability while producing native editable Design layers) and publish the 7-module architecture flow to FigJam via `generate_diagram`.

**Tech Stack:** Node.js `v22.23.4` (native TypeScript stripping + `node:test` + `node:assert/strict`), Figma Plugin API (dynamic-page compatible TypeScript), Figma PropsKit (`fig-*` custom elements), Figma MCP (`generate_diagram`, `create_generative_plugin`, `get_generative_plugin`, `update_generative_plugin`).

**Spec:** `docs/superpowers/specs/2026-11-16-figma-7-modules-ubnd-ai-design.md` (derived from `Profile_gioi_thieu_Bo_Tro_ly_AI_UBND_xa_phuong_TSH.pdf`)

## Global Constraints

- Zero external npm runtime/dev dependencies — use Node `v22.23.4` native TypeScript execution (`node --test`).
- Every generated screen frame MUST be `1440×960` px using Auto Layout (`HORIZONTAL` root: `268px` dark sidebar `#0F172A` + `1172px` main workspace `#F1F5F9`), never flattened raster screenshots.
- All 4 specialized commune/ward departments MUST be supported: `VP` (*Văn phòng HĐND & UBND*), `KT` (*Kinh tế*), `VHXH` (*Văn hóa - Xã hội*), `NNMT` (*Nông nghiệp và Môi trường*).
- All 7 modules from Section III of the TSH Profile MUST be generated as dedicated screens (`01` through `07`) alongside `00 · Design System & Components`.
- Legal accountability copy MUST appear verbatim: `"AI là công cụ hỗ trợ nghiệp vụ; cán bộ, công chức và người có thẩm quyền vẫn trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."`
- `dist/code.ts` MUST be a single standalone TypeScript file with zero `import`/`export` statements, zero secrets/network calls, normalized `0..1` RGB paints without `a` inside `color`, and dynamic-page-compatible async Figma APIs.
- Target Figma Plan Key is `"team::1703004690588386734"`.

## Review Focus

1. **Missing font style (`"Inter SemiBold"` vs `"Inter Semi Bold"` or missing weight in user environment):** `loadFontsSafe()` must attempt `{ family: "Inter", style: "Semi Bold" }` first and fall back cleanly to `"Bold"` / `"Regular"` instead of throwing an unhandled font error. *(Pinned in Task 2)*
2. **Figma Auto-Layout sizing order (`FILL` before `appendChild`) & collapsing wrapped Vietnamese text:** `createAutoFrame` and `createTextNode` must append the child to an auto-layout parent BEFORE setting `layoutSizingHorizontal = "FILL"`, and set `textAutoResize = "HEIGHT"` whenever `fillHorizontal: true` on `TEXT`. *(Pinned in Task 2)*
3. **SVG icons using `currentColor` or lacking `width`/`height`/`viewBox`:** `createSvgIcon()` must emit explicit `#RRGGBB` stroke/fill colors and explicit `width`, `height`, and `viewBox="0 0 24 24"` so icons never turn black on the `#0F172A` sidebar or mis-scale. *(Pinned in Task 2)*
4. **Canvas collision on repeat runs or invalid UI parameters:** `computeCanvasOrigin()` must place new frames `160px` to the right of existing `figma.currentPage.children` (or centered around `figma.viewport.center` on an empty page) and coerce unknown `scope`/`departmentId` values safely to `"ALL"` / `"VP"`. *(Pinned in Task 6)*
5. **Bundled `dist/code.ts` leaking ESM `import`/`export` keywords or invalid TypeScript:** `scripts/bundle-plugin.ts` output must contain zero module `import`/`export` declarations while keeping valid TypeScript types accepted by `update_generative_plugin`. *(Pinned in Task 6)*

---

## File Structure

- `package.json` — Minimal ESM manifest (`"type": "module"`, scripts `test` and `bundle`) with zero `dependencies`/`devDependencies`.
- `.gitignore` — Ignores `dist/`, `.DS_Store`, `node_modules/`.
- `src/figma-plugin/tokens.ts` — Design tokens: 16 hex/RGB `0..1` colors, typography scale, `1440×960` layout constants, `DepartmentId`, `ModuleId`, `NavItemId`.
- `src/figma-plugin/modules-data.ts` — Structured Vietnamese copy from the TSH Profile: 4 departments, 12 sidebar nav items mapped to 7 modules, module summaries, legal disclaimer, and realistic administrative sample rows (including `Nghị định 399/2026/NĐ-CP` and `Nghị định 30/2020/NĐ-CP`).
- `src/figma-plugin/primitives.ts` — Safe Figma Plugin API wrappers: `loadFontsSafe`, `solidPaint`, `createAutoFrame`, `createTextNode`, `createSvgIcon`, `ensureDesignVariables`.
- `src/figma-plugin/shell.ts` — `buildDesignSystemScreen` (`00 · Design System & Components` + reusable Figma `COMPONENT`s) and `createAppShell` (`268px` sidebar + `1172×68` top header + `892px` workspace body).
- `src/figma-plugin/screens-ai-authoring.ts` — Screen builders for Modules `01` (*Trợ lý AI theo nghiệp vụ*), `02` (*AI kiến thức mở rộng*), and `03` (*Soạn thảo và kiểm tra*).
- `src/figma-plugin/screens-ops-admin.ts` — Screen builders for Modules `04` (*Nguồn văn bản chính thức*), `05` (*Tải và xử lý tài liệu*), `06` (*Điều hành công việc*), and `07` (*Phân quyền & Nhân bản AI*).
- `src/figma-plugin/entry.ts` — Plugin sandbox entrypoint: `computeCanvasOrigin`, `generateScreens`, `bootPlugin` (`figma.showUI`, message handler, `setRelaunchData`).
- `src/figma-plugin/ui.html` — PropsKit UI (`<fig-content>`, `<fig-dropdown>` for scope & department, `<fig-switch>` for Design System sheet, `<fig-footer>` status + primary submit button).
- `scripts/bundle-plugin.ts` — Concatenates `src/figma-plugin/*.ts` in topological order, strips `import`/`export` syntax, emits `dist/code.ts` + `dist/ui.html`.
- `tests/helpers/figma-mock.ts` — In-memory Figma Plugin API mock enforcing font loading, `0..1` RGB bounds, `appendChild`-before-`FILL`, and SVG attribute rules.
- `tests/tokens-and-data.test.ts` — Unit tests for Task 1.
- `tests/primitives.test.ts` — Unit tests for Task 2 (including Review Focus #1, #2, #3).
- `tests/shell.test.ts` — Unit tests for Task 3.
- `tests/screens-01-03.test.ts` — Unit tests for Task 4.
- `tests/screens-04-07.test.ts` — Unit tests for Task 5.
- `tests/plugin-bundle.test.ts` — Integration & bundle verification tests for Task 6 (including Review Focus #4, #5).
- `docs/figma-links.md` — Recorded live FigJam diagram URL + Figma Design 1-click plugin launch URL from Task 7.

---

### Task 1: Project Scaffolding, Design Tokens & 7-Module Data Spec

**Files:**
- Create: `.gitignore`
- Create: `package.json`
- Create: `src/figma-plugin/tokens.ts`
- Create: `src/figma-plugin/modules-data.ts`
- Test: `tests/tokens-and-data.test.ts`

**Interfaces:**
- Consumes: Spec Sections 3, 4, 5 (`docs/superpowers/specs/2026-11-16-figma-7-modules-ubnd-ai-design.md`)
- Produces:
  - `tokens.ts`:
    - `export type RGBColor = { readonly r: number; readonly g: number; readonly b: number };`
    - `export type DepartmentId = "VP" | "KT" | "VHXH" | "NNMT";`
    - `export type ModuleId = "M01" | "M02" | "M03" | "M04" | "M05" | "M06" | "M07";`
    - `export type NavItemId = "nav-m01" | "nav-m02" | "nav-m03" | "nav-m04" | "nav-m05" | "nav-m06" | "nav-doc-req" | "nav-instruction" | "nav-api" | "nav-rbac" | "nav-audit-log" | "nav-clone";`
    - `export type IconName = "plus" | "sparkles" | "file-check" | "book-open" | "upload" | "check-square" | "refresh" | "sliders" | "link" | "shield" | "clock" | "copy" | "search" | "alert";`
    - `export function hexToRgb(hex: string): RGBColor;`
    - `export const HEX_PALETTE: Record<string, string>;`
    - `export const COLORS: Record<string, RGBColor>;`
    - `export const LAYOUT: { readonly SCREEN_W: 1440; readonly SCREEN_H: 960; readonly SIDEBAR_W: 268; readonly MAIN_W: 1172; readonly HEADER_H: 68; readonly BODY_H: 892; readonly CANVAS_GAP: 160 };`
  - `modules-data.ts`:
    - `export interface DepartmentSpec { id: DepartmentId; code: string; name: string; scopeSummary: string; }`
    - `export interface SidebarNavSpec { id: NavItemId; label: string; moduleId: ModuleId; section: "core" | "admin"; iconName: IconName; }`
    - `export interface ModuleSummarySpec { id: ModuleId; order: string; frameName: string; title: string; subtitle: string; activeNavId: NavItemId; }`
    - `export const DEPARTMENTS: Record<DepartmentId, DepartmentSpec>;`
    - `export const SIDEBAR_NAV_ITEMS: readonly SidebarNavSpec[];`
    - `export const MODULE_SUMMARIES: readonly ModuleSummarySpec[];`
    - `export const LEGAL_DISCLAIMER: string;`

- [ ] **Step 1: Initialize Git repository, `.gitignore`, and `package.json`**

Run `git init` in `/home/fedora/Documents/UBND-AI-Support` if `.git` does not exist. Create `.gitignore` (`dist/`, `node_modules/`, `.DS_Store`) and `package.json` with `"type": "module"`, `"scripts": { "test": "node --test tests/*.test.ts", "bundle": "node scripts/bundle-plugin.ts" }`.

- [ ] **Step 2: Write the failing test in `tests/tokens-and-data.test.ts`**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { HEX_PALETTE, COLORS, LAYOUT, hexToRgb } from "../src/figma-plugin/tokens.ts";
import { DEPARTMENTS, SIDEBAR_NAV_ITEMS, MODULE_SUMMARIES, LEGAL_DISCLAIMER } from "../src/figma-plugin/modules-data.ts";

test("tokens normalize all 16 spec colors into 0..1 RGB without alpha", () => {
  assert.equal(Object.keys(HEX_PALETTE).length, 16);
  for (const [key, rgb] of Object.entries(COLORS)) {
    assert.ok(rgb.r >= 0 && rgb.r <= 1, `${key}.r out of range`);
    assert.ok(rgb.g >= 0 && rgb.g <= 1, `${key}.g out of range`);
    assert.ok(rgb.b >= 0 && rgb.b <= 1, `${key}.b out of range`);
    assert.equal("a" in rgb, false);
  }
  assert.deepEqual(hexToRgb("#FFFFFF"), { r: 1, g: 1, b: 1 });
  assert.equal(LAYOUT.SIDEBAR_W + LAYOUT.MAIN_W, LAYOUT.SCREEN_W);
  assert.equal(LAYOUT.HEADER_H + LAYOUT.BODY_H, LAYOUT.SCREEN_H);
});

test("modules-data covers all 4 departments, 7 modules, 12 sidebar items, and verbatim disclaimer", () => {
  assert.deepEqual(Object.keys(DEPARTMENTS), ["VP", "KT", "VHXH", "NNMT"]);
  assert.equal(MODULE_SUMMARIES.length, 7);
  assert.equal(SIDEBAR_NAV_ITEMS.length, 12);
  assert.ok(LEGAL_DISCLAIMER.includes("trực tiếp kiểm tra, quyết định và chịu trách nhiệm"));
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test tests/tokens-and-data.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `../src/figma-plugin/tokens.ts`.

- [ ] **Step 4: Implement `src/figma-plugin/tokens.ts` and `src/figma-plugin/modules-data.ts`**

Populate all 16 hex tokens from Spec Section 3.1, `hexToRgb`, `LAYOUT`, the 4 `DEPARTMENTS` from Spec Section 4, the 12 `SIDEBAR_NAV_ITEMS` matching the TSH PDF screenshot (`+ Tư vấn công việc`, `AI hỗ trợ kiến thức mở rộng`, `Soạn thảo & kiểm tra`, `Nguồn văn bản chính thức`, `Tải & xử lý tài liệu phiên`, `Điều hành công việc`, `Đề nghị cập nhật văn bản`, `Instruction của phòng`, `Cổng API đấu nối`, `Phân quyền email`, `Nhật ký hệ thống`, `Nhân bản AI`), `MODULE_SUMMARIES` (`M01`..`M07`), and `LEGAL_DISCLAIMER`.

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test tests/tokens-and-data.test.ts`
Expected: PASS (2/2 passing).

- [ ] **Step 6: Commit**

```bash
git add .gitignore package.json docs/superpowers/ src/figma-plugin/tokens.ts src/figma-plugin/modules-data.ts tests/tokens-and-data.test.ts
git commit -m "feat: add design tokens and 7-module data specification"
```

---

### Task 2: Mock Figma Runtime & Safe Plugin Primitives

**Files:**
- Create: `tests/helpers/figma-mock.ts`
- Create: `src/figma-plugin/primitives.ts`
- Test: `tests/primitives.test.ts`

**Interfaces:**
- Consumes: `RGBColor`, `IconName`, `HEX_PALETTE`, `COLORS` from `src/figma-plugin/tokens.ts`
- Produces:
  - `tests/helpers/figma-mock.ts`:
    - `export function installFigmaMock(opts?: { rejectFonts?: string[] }): { figma: any; loadedFonts: string[]; createdSvgs: string[] };`
  - `src/figma-plugin/primitives.ts`:
    - `export interface FontSpec { family: string; style: string; }`
    - `export interface LoadedFonts { regular: FontSpec; medium: FontSpec; semiBold: FontSpec; bold: FontSpec; }`
    - `export interface ReusableComponents { sidebarItem: any; sidebarItemActive: any; primaryButton: any; secondaryButton: any; statusBadge: any; kpiCard: any; }`
    - `export interface BuilderContext { fonts: LoadedFonts; components?: ReusableComponents; variables?: Record<string, any>; }`
    - `export async function loadFontsSafe(): Promise<LoadedFonts>;`
    - `export function solidPaint(color: RGBColor, opacity?: number): { type: "SOLID"; color: RGBColor; opacity?: number };`
    - `export function createAutoFrame(opts: { name: string; direction: "HORIZONTAL" | "VERTICAL"; padding?: number | [number, number, number, number]; gap?: number; fill?: RGBColor; stroke?: RGBColor; radius?: number; width?: number; height?: number; parent?: any; fillHorizontal?: boolean; fillVertical?: boolean; alignPrimary?: "MIN" | "CENTER" | "MAX" | "SPACE_BETWEEN"; alignCounter?: "MIN" | "CENTER" | "MAX"; clip?: boolean; }): any;`
    - `export function createTextNode(opts: { text: string; font: FontSpec; size: number; lineHeight?: number; color: RGBColor; parent?: any; fillHorizontal?: boolean; name?: string; }): any;`
    - `export function createSvgIcon(name: IconName, size: number, hexColor: string, parent?: any): any;`
    - `export async function ensureDesignVariables(): Promise<Record<string, any>>;`

- [ ] **Step 1: Write the failing test in `tests/primitives.test.ts` (pinning Review Focus #1, #2, #3)**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { installFigmaMock } from "./helpers/figma-mock.ts";
import { loadFontsSafe, createAutoFrame, createTextNode, createSvgIcon, ensureDesignVariables } from "../src/figma-plugin/primitives.ts";
import { COLORS } from "../src/figma-plugin/tokens.ts";

test("Review Focus #1: loadFontsSafe falls back cleanly when Inter Semi Bold is unavailable", async () => {
  installFigmaMock({ rejectFonts: ["Inter::Semi Bold"] });
  const fonts = await loadFontsSafe();
  assert.equal(fonts.semiBold.family, "Inter");
  assert.equal(fonts.semiBold.style, "Bold");
});

test("Review Focus #2: createAutoFrame and createTextNode append before FILL and set HEIGHT auto-resize", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const parent = createAutoFrame({ name: "Parent", direction: "VERTICAL", width: 400 });
  const child = createAutoFrame({ name: "Child", direction: "HORIZONTAL", parent, fillHorizontal: true });
  const label = createTextNode({ text: "Văn phòng HĐND & UBND", font: fonts.regular, size: 13, color: COLORS["text-primary"], parent: child, fillHorizontal: true });
  assert.equal(child.layoutSizingHorizontal, "FILL");
  assert.equal(label.layoutSizingHorizontal, "FILL");
  assert.equal(label.textAutoResize, "HEIGHT");
});

test("Review Focus #3: createSvgIcon injects explicit width, height, viewBox, and hex stroke without currentColor", () => {
  const { createdSvgs } = installFigmaMock();
  const icon = createSvgIcon("sparkles", 20, "#60A5FA");
  assert.equal(icon.width, 20);
  assert.equal(createdSvgs.length, 1);
  assert.match(createdSvgs[0], /width="20"/);
  assert.match(createdSvgs[0], /viewBox="0 0 24 24"/);
  assert.match(createdSvgs[0], /#60A5FA/);
  assert.doesNotMatch(createdSvgs[0], /currentColor/);
});

test("ensureDesignVariables creates UBnd-AI-Tokens collection with 16 color variables", async () => {
  installFigmaMock();
  const vars = await ensureDesignVariables();
  assert.equal(Object.keys(vars).length, 16);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/primitives.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement `tests/helpers/figma-mock.ts` and `src/figma-plugin/primitives.ts`**

- In `figma-mock.ts`: Throw if `characters` or `fontName` is assigned before `loadFontAsync` resolved that `"family::style"`; throw if `layoutSizingHorizontal` / `layoutSizingVertical` is set to `"FILL"` when `node.parent` is null or lacks `layoutMode`; throw if any paint color channel is `< 0` or `> 1` or contains `'a'`; throw if `createNodeFromSvg` lacks `width=`, `height=`, `viewBox=`, or contains `currentColor`. Support `createComponent()`, `component.createInstance()`, `variables.getLocalVariableCollectionsAsync()`, `variables.createVariableCollection()`, `variables.createVariable()`.
- In `primitives.ts`: Implement `loadFontsSafe` (loads `Regular`, `Medium`, `Bold`, then tries `Semi Bold` with fallback to `Bold`), `solidPaint`, `createAutoFrame` (sets `layoutMode`, `resize` BEFORE `appendChild` and `layoutSizing* = "FILL"` AFTER `appendChild`), `createTextNode` (sets `fontName` → `characters` → `fontSize` → `lineHeight` → `fills` → `appendChild` → `textAutoResize = "HEIGHT"` + `layoutSizingHorizontal = "FILL"`), `createSvgIcon` for all 14 `IconName` paths, and `ensureDesignVariables` with explicit `scopes`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/primitives.test.ts`
Expected: PASS (4/4 passing).

- [ ] **Step 5: Commit**

```bash
git add tests/helpers/figma-mock.ts src/figma-plugin/primitives.ts tests/primitives.test.ts
git commit -m "feat: add mock Figma runtime and safe plugin primitives"
```

---

### Task 3: Design System Sheet (`00`) & Shared Application Shell

**Files:**
- Create: `src/figma-plugin/shell.ts`
- Test: `tests/shell.test.ts`

**Interfaces:**
- Consumes: `LAYOUT`, `COLORS`, `HEX_PALETTE`, `DepartmentId`, `NavItemId` from `tokens.ts`; `DEPARTMENTS`, `SIDEBAR_NAV_ITEMS`, `LEGAL_DISCLAIMER` from `modules-data.ts`; `BuilderContext`, `ReusableComponents`, `createAutoFrame`, `createTextNode`, `createSvgIcon` from `primitives.ts`
- Produces (`src/figma-plugin/shell.ts`):
  - `export interface AppShellResult { screenFrame: any; sidebarFrame: any; headerFrame: any; bodyFrame: any; }`
  - `export function buildDesignSystemScreen(ctx: BuilderContext, x: number, y: number): { frame: any; components: ReusableComponents };`
  - `export function createAppShell(ctx: BuilderContext, opts: { frameName: string; activeNavId: NavItemId; departmentId: DepartmentId; x: number; y: number; headerSubtitle?: string; }): AppShellResult;`

- [ ] **Step 1: Write the failing test in `tests/shell.test.ts`**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { installFigmaMock } from "./helpers/figma-mock.ts";
import { loadFontsSafe } from "../src/figma-plugin/primitives.ts";
import { buildDesignSystemScreen, createAppShell } from "../src/figma-plugin/shell.ts";

test("buildDesignSystemScreen creates 1440x960 frame and 6 reusable Figma components", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const { frame, components } = buildDesignSystemScreen({ fonts }, 0, 0);
  assert.equal(frame.name, "00 · Design System & Components");
  assert.equal(frame.width, 1440);
  assert.equal(frame.height, 960);
  assert.equal(components.primaryButton.type, "COMPONENT");
  assert.equal(components.kpiCard.type, "COMPONENT");
});

test("createAppShell builds 268px sidebar with 12 nav items, department workspace, and 1172px main area", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const ds = buildDesignSystemScreen({ fonts }, 0, 0);
  const shell = createAppShell({ fonts, components: ds.components }, {
    frameName: "01 · Trợ lý AI theo nghiệp vụ",
    activeNavId: "nav-m01",
    departmentId: "VP",
    x: 1600,
    y: 0,
  });
  assert.equal(shell.screenFrame.width, 1440);
  assert.equal(shell.sidebarFrame.width, 268);
  assert.equal(shell.headerFrame.height, 68);
  const allTexts = shell.screenFrame.findAll((n: any) => n.type === "TEXT").map((n: any) => n.characters).join(" | ");
  assert.match(allTexts, /TRỢ LÝ CÁN BỘ/);
  assert.match(allTexts, /Văn phòng HĐND & UBND/);
  assert.match(allTexts, /tsh\.co@tshorg\.vn/);
  assert.match(allTexts, /UBND CẤP XÃ · HỆ THỐNG NỘI BỘ/);
  assert.match(allTexts, /\+ Kiểm tra văn bản/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/shell.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `../src/figma-plugin/shell.ts`.

- [ ] **Step 3: Implement `src/figma-plugin/shell.ts`**

Implement `buildDesignSystemScreen` (renders 16 color swatches, Vietnamese typography scale, and creates reusable `COMPONENT` nodes `Comp/SidebarItem`, `Comp/SidebarItemActive`, `Comp/PrimaryButton`, `Comp/SecondaryButton`, `Comp/StatusBadge`, `Comp/KpiCard`) and `createAppShell` (renders `1440×960` root frame at `(x, y)`, `268px` `#0F172A` sidebar with `TRỢ LÝ CÁN BỘ`, `KHÔNG GIAN LÀM VIỆC` selector for `departmentId`, 12 nav items instantiating `sidebarItemActive` for `activeNavId`, `tsh.co@tshorg.vn` footer, plus `1172px` right column with `68px` top bar and `892px` `bodyFrame` including the footer legal disclaimer bar).

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/shell.test.ts`
Expected: PASS (2/2 passing).

- [ ] **Step 5: Commit**

```bash
git add src/figma-plugin/shell.ts tests/shell.test.ts
git commit -m "feat: implement design system frame and shared UBND AI app shell"
```

---

### Task 4: Core AI & Document Authoring Screens (Modules 01, 02, 03)

**Files:**
- Create: `src/figma-plugin/screens-ai-authoring.ts`
- Test: `tests/screens-01-03.test.ts`

**Interfaces:**
- Consumes: `BuilderContext`, `createAutoFrame`, `createTextNode`, `createSvgIcon` from `primitives.ts`; `createAppShell` from `shell.ts`; `DepartmentId`, `COLORS` from `tokens.ts`; `DEPARTMENTS` from `modules-data.ts`
- Produces (`src/figma-plugin/screens-ai-authoring.ts`):
  - `export function buildModule01Assistant(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`
  - `export function buildModule02ExtendedKnowledge(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`
  - `export function buildModule03DraftingAndAudit(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`

- [ ] **Step 1: Write the failing test in `tests/screens-01-03.test.ts`**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { installFigmaMock } from "./helpers/figma-mock.ts";
import { loadFontsSafe } from "../src/figma-plugin/primitives.ts";
import { buildDesignSystemScreen } from "../src/figma-plugin/shell.ts";
import { buildModule01Assistant, buildModule02ExtendedKnowledge, buildModule03DraftingAndAudit } from "../src/figma-plugin/screens-ai-authoring.ts";

const dumpText = (root: any) => root.findAll((n: any) => n.type === "TEXT").map((n: any) => n.characters).join(" | ");

test("Module 01 renders exact TSH workspace modes, empty-state pills, and composer", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const { components } = buildDesignSystemScreen({ fonts }, 0, 0);
  const frame = buildModule01Assistant({ fonts, components }, "VP", 1600, 0);
  const text = dumpText(frame);
  assert.equal(frame.name, "01 · Mô-đun 01: Trợ lý AI theo nghiệp vụ");
  for (const phrase of ["Anh/chị cần xử lý công việc gì?", "Kết thúc phiên - Xóa bộ nhớ", "Soạn thảo nhanh", "Tư vấn nghiệp vụ", "Thẩm định chuyên sâu", "Ta nên bắt đầu việc gì?", "Tài liệu chỉ được dùng trong phiên hiện tại"]) {
    assert.ok(text.includes(phrase), `Missing phrase: ${phrase}`);
  }
});

test("Module 02 renders extended knowledge banner and 3 multi-option analysis cards", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const frame = buildModule02ExtendedKnowledge({ fonts }, "VP", 3200, 0);
  const text = dumpText(frame);
  assert.equal(frame.name, "02 · Mô-đun 02: AI kiến thức mở rộng");
  assert.match(text, /Phương án A/);
  assert.match(text, /Phương án B/);
  assert.match(text, /Phương án C/);
});

test("Module 03 renders split Decree 30/2020 draft editor and 5-criteria AI audit panel", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const frame = buildModule03DraftingAndAudit({ fonts }, "VP", 4800, 0);
  const text = dumpText(frame);
  assert.equal(frame.name, "03 · Mô-đun 03: Soạn thảo và kiểm tra");
  assert.match(text, /CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM/);
  assert.match(text, /30\/2020\/NĐ-CP/);
  assert.match(text, /399\/2026\/NĐ-CP/);
  assert.match(text, /Thẩm quyền ban hành/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/screens-01-03.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement `src/figma-plugin/screens-ai-authoring.ts`**

Implement `buildModule01Assistant`, `buildModule02ExtendedKnowledge`, and `buildModule03DraftingAndAudit` per Spec Section 5 (`01`, `02`, `03`), adapting the workspace eyebrow/title dynamically to `DEPARTMENTS[departmentId]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/screens-01-03.test.ts`
Expected: PASS (3/3 passing).

- [ ] **Step 5: Commit**

```bash
git add src/figma-plugin/screens-ai-authoring.ts tests/screens-01-03.test.ts
git commit -m "feat: implement Figma builders for modules 01, 02, and 03"
```

---

### Task 5: Data Repository, Session Docs, Task Ops & RBAC Screens (Modules 04, 05, 06, 07)

**Files:**
- Create: `src/figma-plugin/screens-ops-admin.ts`
- Test: `tests/screens-04-07.test.ts`

**Interfaces:**
- Consumes: `BuilderContext`, `createAutoFrame`, `createTextNode`, `createSvgIcon` from `primitives.ts`; `createAppShell` from `shell.ts`; `DepartmentId`, `COLORS` from `tokens.ts`; `DEPARTMENTS` from `modules-data.ts`
- Produces (`src/figma-plugin/screens-ops-admin.ts`):
  - `export function buildModule04OfficialDocs(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`
  - `export function buildModule05DocumentSession(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`
  - `export function buildModule06TaskManagement(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`
  - `export function buildModule07RbacAndClone(ctx: BuilderContext, departmentId: DepartmentId, x: number, y: number): any;`

- [ ] **Step 1: Write the failing test in `tests/screens-04-07.test.ts`**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { installFigmaMock } from "./helpers/figma-mock.ts";
import { loadFontsSafe } from "../src/figma-plugin/primitives.ts";
import { buildDesignSystemScreen } from "../src/figma-plugin/shell.ts";
import {
  buildModule04OfficialDocs,
  buildModule05DocumentSession,
  buildModule06TaskManagement,
  buildModule07RbacAndClone,
} from "../src/figma-plugin/screens-ops-admin.ts";

const dumpText = (root: any) => root.findAll((n: any) => n.type === "TEXT").map((n: any) => n.characters).join(" | ");

test("Modules 04, 05, 06, 07 render all required domain sections and 1440x960 dimensions", async () => {
  installFigmaMock();
  const fonts = await loadFontsSafe();
  const { components } = buildDesignSystemScreen({ fonts }, 0, 0);
  const ctx = { fonts, components };

  const m04 = buildModule04OfficialDocs(ctx, "VP", 6400, 0);
  assert.equal(m04.name, "04 · Mô-đun 04: Nguồn văn bản chính thức");
  assert.match(dumpText(m04), /Nghị định 399\/2026\/NĐ-CP/);
  assert.match(dumpText(m04), /Kho dữ liệu riêng/);

  const m05 = buildModule05DocumentSession(ctx, "NNMT", 8000, 0);
  assert.equal(m05.name, "05 · Mô-đun 05: Tải và xử lý tài liệu");
  assert.match(dumpText(m05), /Nông nghiệp và Môi trường/);
  assert.match(dumpText(m05), /Đối chiếu/);

  const m06 = buildModule06TaskManagement(ctx, "KT", 9600, 0);
  assert.equal(m06.name, "06 · Mô-đun 06: Điều hành công việc");
  assert.match(dumpText(m06), /Giao nhiệm vụ mới/);
  assert.match(dumpText(m06), /93,7%/);

  const m07 = buildModule07RbacAndClone(ctx, "VP", 11200, 0);
  assert.equal(m07.name, "07 · Mô-đun 07: Phân quyền & Nhân bản hệ thống");
  assert.match(dumpText(m07), /Nhân bản hệ thống AI độc lập/);
  assert.match(dumpText(m07), /Văn hóa - Xã hội/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/screens-04-07.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement `src/figma-plugin/screens-ops-admin.ts`**

Implement `buildModule04OfficialDocs`, `buildModule05DocumentSession`, `buildModule06TaskManagement` (instantiating `ctx.components?.kpiCard` when present), and `buildModule07RbacAndClone` per Spec Section 5 (`04`–`07`).

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/screens-04-07.test.ts`
Expected: PASS (1/1 passing).

- [ ] **Step 5: Commit**

```bash
git add src/figma-plugin/screens-ops-admin.ts tests/screens-04-07.test.ts
git commit -m "feat: implement Figma builders for modules 04, 05, 06, and 07"
```

---

### Task 6: Plugin Sandbox Entrypoint, PropsKit UI & Single-File Bundler

**Files:**
- Create: `src/figma-plugin/entry.ts`
- Create: `src/figma-plugin/ui.html`
- Create: `scripts/bundle-plugin.ts`
- Test: `tests/plugin-bundle.test.ts`

**Interfaces:**
- Consumes: All builders from `tokens.ts`, `modules-data.ts`, `primitives.ts`, `shell.ts`, `screens-ai-authoring.ts`, `screens-ops-admin.ts`
- Produces:
  - `src/figma-plugin/entry.ts`:
    - `export type PluginScope = "ALL" | ModuleId;`
    - `export interface GenerateRequest { type: "generate"; scope: PluginScope; departmentId: DepartmentId; includeDesignSystem: boolean; }`
    - `export type UiInboundMessage = { type: "resize"; height: number } | GenerateRequest;`
    - `export function computeCanvasOrigin(children: readonly { x: number; y: number; width: number }[], viewportCenter: { x: number; y: number }): { x: number; y: number };`
    - `export async function generateScreens(req: GenerateRequest, onProgress?: (msg: string) => void): Promise<any[]>;`
    - `export function bootPlugin(): void;`
  - `dist/code.ts` & `dist/ui.html` emitted by `node scripts/bundle-plugin.ts`

- [ ] **Step 1: Write the failing test in `tests/plugin-bundle.test.ts` (pinning Review Focus #4, #5)**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { installFigmaMock } from "./helpers/figma-mock.ts";
import { computeCanvasOrigin, generateScreens } from "../src/figma-plugin/entry.ts";

test("Review Focus #4: computeCanvasOrigin avoids overlapping existing frames and generateScreens clamps invalid inputs", async () => {
  installFigmaMock();
  const emptyOrigin = computeCanvasOrigin([], { x: 1000, y: 500 });
  assert.equal(emptyOrigin.x, 280);
  const nextOrigin = computeCanvasOrigin([{ x: 280, y: 20, width: 1440 }], { x: 1000, y: 500 });
  assert.equal(nextOrigin.x, 280 + 1440 + 160);

  const allFrames = await generateScreens({
    type: "generate",
    scope: "INVALID" as any,
    departmentId: "UNKNOWN" as any,
    includeDesignSystem: true,
  });
  assert.equal(allFrames.length, 8);
});

test("Review Focus #5: bundle-plugin produces single-file dist/code.ts with zero imports/exports and valid PropsKit dist/ui.html", () => {
  execFileSync(process.execPath, ["scripts/bundle-plugin.ts"], { stdio: "pipe" });
  const codeTs = fs.readFileSync(path.resolve("dist/code.ts"), "utf8");
  const uiHtml = fs.readFileSync(path.resolve("dist/ui.html"), "utf8");

  assert.doesNotMatch(codeTs, /^\s*import\s+/m);
  assert.doesNotMatch(codeTs, /^\s*export\s+/m);
  assert.match(codeTs, /bootPlugin\(\)/);
  assert.match(codeTs, /setRelaunchData/);
  assert.match(uiHtml, /<fig-content>/);
  assert.match(uiHtml, /<fig-dropdown/);
  assert.match(uiHtml, /<fig-button[^>]*type="submit"/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/plugin-bundle.test.ts`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `../src/figma-plugin/entry.ts`.

- [ ] **Step 3: Implement `src/figma-plugin/entry.ts`, `src/figma-plugin/ui.html`, and `scripts/bundle-plugin.ts`**

- `entry.ts`: Validate/clamp `scope` (`"ALL"` or `"M01"`..`"M07"`) and `departmentId` (`"VP"` | `"KT"` | `"VHXH"` | `"NNMT"`). Implement `computeCanvasOrigin` (`children.length === 0 ? { x: Math.round(viewportCenter.x - 720), y: Math.round(viewportCenter.y - 480) } : { x: Math.max(...children.map(c => c.x + c.width)) + 160, y: children[0].y }`). Build requested screens sequentially `1600px` apart (`1440 + 160`), post progress status messages (`figma.ui.postMessage({ type: "status", text })`), set `figma.root.setRelaunchData({ open: "Mở trình vẽ 7 mô-đun UBND AI" })`, attach relaunch data to created frames, select generated frames, and `figma.viewport.scrollAndZoomIntoView(created)`.
- `ui.html`: Include `localStorage` sandbox shim, PropsKit `<fig-content>` with `<fig-dropdown id="scope">` (`Tất cả 7 mô-đun` + individual `M01..M07`), `<fig-dropdown id="department">` (4 departments), `<fig-switch id="include-ds" checked>`, and `<fig-footer>` with status `<label id="status">` + `<fig-button id="run" type="submit">Create layers</fig-button>`.
- `scripts/bundle-plugin.ts`: Concatenate `tokens.ts`, `modules-data.ts`, `primitives.ts`, `shell.ts`, `screens-ai-authoring.ts`, `screens-ops-admin.ts`, `entry.ts` in dependency order, strip module `import ...;` statements and leading `export ` keywords, append `bootPlugin();\n`, and write `dist/code.ts` + copy `src/figma-plugin/ui.html` to `dist/ui.html`.

- [ ] **Step 4: Run full test suite to verify everything passes**

Run: `npm test`
Expected: PASS across all 6 test files with 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/figma-plugin/entry.ts src/figma-plugin/ui.html scripts/bundle-plugin.ts tests/plugin-bundle.test.ts
git commit -m "feat: add Figma plugin UI, entrypoint, and single-file bundler"
```

---

### Task 7: Deploy FigJam 7-Module Flow Diagram & Publish Figma Design Plugin

**Files:**
- Create: `docs/figma-links.md`

**Interfaces:**
- Consumes: `dist/code.ts`, `dist/ui.html`, Figma MCP tools (`generate_diagram`, `create_generative_plugin`, `get_generative_plugin`, `update_generative_plugin`), `planKey: "team::1703004690588386734"`
- Produces:
  - Deployed FigJam Architecture & Workflow Diagram URL
  - Deployed Figma Design Plugin (`id`, `version`, and clickable 1-click launch URL `https://www.figma.com/file/new?try-tool-resource-content-id=<id>&try-tool-resource-type=gen_tool&type=design&mode=design`)
  - Recorded links and usage instructions in `docs/figma-links.md`

- [ ] **Step 1: Load mandatory Figma MCP skills before tool invocation**

Read `/home/fedora/.gemini/config/plugins/figma/skills/figma-generate-diagram/SKILL.md` and `/home/fedora/.gemini/config/plugins/figma/skills/figma-generative-plugins/SKILL.md` (plus `references/authoring.md` checklist).

- [ ] **Step 2: Publish the 7-Module Workflow Diagram to FigJam via `generate_diagram`**

Call `figma_figma:generate_diagram` with `planKey: "team::1703004690588386734"`, `name: "Quy trinh 7 Mo dun Bo Tro ly AI UBND Xa Phuong"`, and an `LR` `flowchart` Mermaid diagram (quoted node/edge labels, no emojis, no `\n`, no `"end"` classNames) connecting the 4 Department Workspaces (`VP`, `KT`, `VHXH`, `NNMT`) through Modules `01` → `07`. Verify a valid `https://www.figma.com/board/...` URL is returned.

- [ ] **Step 3: Create & inspect the Figma Design Plugin scaffold**

1. Call `figma_figma:create_generative_plugin` with `name: "UBND AI - Bo 7 Mo dun Xa Phuong (TSH)"`, `description: "Sinh trọn bộ 8 màn hình Figma Design (Design System + 7 mô-đun Bộ Trợ lý AI UBND xã, phường)"`, `planKey: "team::1703004690588386734"`.
2. Call `figma_figma:get_generative_plugin` with the returned `id` (and read its source URIs via `read_resource` or `includeSource: true` if needed) to verify `manifest.json` compatibility.

- [ ] **Step 4: Deploy `dist/code.ts` and `dist/ui.html` via `update_generative_plugin`**

Run `npm run bundle`, then call `figma_figma:update_generative_plugin` with `id`, `commitMessage: "Add 7-module UBND AI Design System and screen generator"`, `versionDescription: "Tạo trọn bộ Design System và 7 màn hình mô-đun Bộ Trợ lý AI UBND xã, phường (1440x960 Auto Layout)"`, `versionDetail: "Hỗ trợ chọn từng mô-đun hoặc toàn bộ 7 mô-đun theo 4 không gian phòng ban chuyên môn với Figma Variables và Components tái sử dụng."`, and `files: [{ path: "code.ts", content }, { path: "ui.html", content }]`. Confirm zero TypeScript compilation errors in the MCP response.

- [ ] **Step 5: Record live Figma URLs in `docs/figma-links.md` and commit**

Write `docs/figma-links.md` containing the live FigJam diagram link, the plugin `id` & `version`, and the clickable Figma Design try-link (`https://www.figma.com/file/new?try-tool-resource-content-id=<id>&try-tool-resource-type=gen_tool&type=design&mode=design`).

```bash
git add docs/figma-links.md
git commit -m "docs: record deployed Figma Design plugin and FigJam diagram links"
```

