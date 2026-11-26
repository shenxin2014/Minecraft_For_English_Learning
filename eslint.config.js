/** 前端质量规则：限制分支复杂度、函数长度，并要求命名定义写明职责。 */
import js from "@eslint/js";
import globals from "globals";

/** 检查具名函数、类和方法的 JSDoc，匿名事件回调由绑定方法说明。 */
function documentationRule(context) {
  /** 导出定义的注释属于 export 节点，普通方法则直接检查自身。 */
  function check(node) {
    const anchor = node.parent.type === "ExportNamedDeclaration" ? node.parent : node;
    const comments = context.sourceCode.getCommentsBefore(anchor);
    if (!comments.some((comment) => comment.type === "Block" && comment.value.startsWith("*"))) {
      context.report({ node, message: "请使用 JSDoc 说明这个类、函数或方法的单一职责。" });
    }
  }
  return { FunctionDeclaration: check, ClassDeclaration: check, MethodDefinition: check };
}

export default [
  js.configs.recommended,
  {
    files: ["frontend/js/**/*.js", "frontend/tests/**/*.js", "bedrock-pack/**/*.js"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { complexity: ["error", 8], "no-unused-vars": ["error", { argsIgnorePattern: "^_" }] },
  },
  {
    files: ["frontend/js/**/*.js", "bedrock-pack/scripts/**/*.js"],
    plugins: { clarity: { rules: { documented: { create: documentationRule } } } },
    rules: {
      "clarity/documented": "error",
      "max-lines-per-function": ["error", { max: 60, skipBlankLines: true, skipComments: true }],
    },
  },
];
