const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const leafOrder = [
  "cover",
  "statement",
  "authorization",
  "front_note",
  "abstract_cn",
  "abstract_en",
  "toc",
  "body",
  "references",
  "errata",
  "appendix",
  "acknowledgment",
  "resume",
];
const groups = {
  pre_numbering: ["cover", "statement", "authorization", "front_note"],
  front_matter: ["abstract_cn", "abstract_en", "toc"],
  abstracts: ["abstract_cn", "abstract_en"],
  back_matter: ["references", "errata", "appendix", "acknowledgment", "resume"],
  all_numbered_content: [
    "abstract_cn",
    "abstract_en",
    "toc",
    "body",
    "references",
    "errata",
    "appendix",
    "acknowledgment",
    "resume",
  ],
};
const roleTitles = [
  ["cover", ["学位论文", "博士学位论文", "硕士学位论文", "本科毕业论文", "毕业论文", "本科毕业设计", "毕业设计"]],
  ["statement", ["原创性声明", "独创性声明", "学位论文原创性声明", "声明", "承诺书", "诚信承诺书"]],
  ["authorization", ["学位论文版权使用授权书", "版权使用授权书", "授权书"]],
  ["front_note", ["说明", "填表说明", "使用说明", "答辩委员会", "评阅人"]],
  ["abstract_cn", ["摘要", "摘 要"]],
  ["abstract_en", ["Abstract"]],
  ["toc", ["目录", "目 录", "Contents", "Table of Contents"]],
  ["body", ["绪论", "引言"]],
  ["references", ["参考文献", "References", "Bibliography"]],
  ["errata", ["勘误页", "勘误"]],
  ["appendix", ["附录", "Appendix"]],
  ["acknowledgment", ["致谢", "Acknowledgement", "Acknowledgments", "Acknowledgements"]],
  ["resume", ["个人简历", "简历", "在学期间发表的学术论文与研究成果"]],
];

function expand(selectors) {
  const selected = new Set();
  for (const raw of Array.isArray(selectors) ? selectors : []) {
    const value = String(raw || "").trim();
    for (const role of groups[value] || [value]) {
      if (role) selected.add(role);
    }
  }
  return leafOrder.filter((role) => selected.has(role));
}

function migrate(payload) {
  const template = payload.template && typeof payload.template === "object"
    ? payload.template
    : payload;
  const hf = template.header_footer;
  if (!hf || !hf.header || !hf.footer || !hf.page_number_plan) return false;

  const common = expand(hf.suppress_header_footer_selectors);
  const headerHide = Boolean(hf.header.hide_on_cover);
  const footerHide = Boolean(hf.footer.hide_on_cover);
  hf.header.hidden_selectors = Array.isArray(hf.header.hidden_selectors)
    ? expand(hf.header.hidden_selectors)
    : common.length
      ? [...common]
      : headerHide
        ? [...groups.pre_numbering]
        : [];
  hf.footer.hidden_selectors = Array.isArray(hf.footer.hidden_selectors)
    ? expand(hf.footer.hidden_selectors)
    : common.length
      ? [...common]
      : footerHide
        ? [...groups.pre_numbering]
        : [];
  delete hf.header.hide_on_cover;
  delete hf.footer.hide_on_cover;
  delete hf.suppress_header_footer_selectors;

  const pageTemplate = hf.footer.page_number_template || "{page}";
  delete hf.footer.page_number_template;
  const legacyMode = String(hf.footer.content_mode || "page_number");
  hf.page_number_plan.enabled =
    hf.page_number_plan.enabled !== undefined
      ? Boolean(hf.page_number_plan.enabled)
      : Boolean(hf.footer.enabled) &&
        ["page_number", "page_number_with_text"].includes(legacyMode);
  hf.page_number_plan.template = hf.page_number_plan.template || pageTemplate;
  hf.page_number_plan.alignment =
    hf.page_number_plan.alignment || hf.footer.alignment || "center";
  hf.footer.content_mode = ["fixed", "page_number_with_text"].includes(legacyMode)
    ? "fixed"
    : "none";

  const phases = Array.isArray(hf.page_number_plan.phases)
    ? hf.page_number_plan.phases
    : [];
  for (const phase of phases) phase.selectors = expand(phase.selectors);
  const covered = new Set(phases.flatMap((phase) => phase.selectors || []));
  const hiddenUncovered = common.filter((role) => !covered.has(role));
  if (hiddenUncovered.length) {
    phases.unshift({
      phase_id: "pre_numbering",
      selectors: hiddenUncovered,
      visible: false,
      number_format: "decimal",
      start_mode: "restart",
      start_value: 1,
    });
  }
  hf.page_number_plan.phases = phases;

  template.section = template.section || { section_break_type: null };
  template.section.semantics_version = 1;
  template.section.roles = Object.fromEntries(
    roleTitles.map(([role, titles], order) => [
      role,
      {
        enabled: true,
        order,
        exact_titles: [...titles],
        anchors: [...titles],
      },
    ]),
  );
  return true;
}

function collectJsonFiles(start) {
  if (!fs.existsSync(start)) return [];
  const result = [];
  for (const entry of fs.readdirSync(start, { withFileTypes: true })) {
    const target = path.join(start, entry.name);
    if (entry.isDirectory()) result.push(...collectJsonFiles(target));
    else if (entry.isFile() && entry.name.endsWith(".json")) result.push(target);
  }
  return result;
}

const files = [
  ...collectJsonFiles(path.join(root, "config_library", "templates")),
  ...collectJsonFiles(path.join(root, "config_library", "template_workbench")),
];
let changed = 0;
for (const file of files) {
  const payload = JSON.parse(fs.readFileSync(file, "utf8"));
  if (!migrate(payload)) continue;
  fs.writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  changed += 1;
}
process.stdout.write(`migrated ${changed} template JSON files\n`);
