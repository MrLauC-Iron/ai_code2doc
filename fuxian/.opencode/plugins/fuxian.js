/**
 * Fuxian 插件 — opencode 版本
 *
 * 在 opencode 中注入 fuxian 引导上下文并自动注册技能目录。
 */

import path from 'path';
import fs from 'fs';
import os from 'os';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 简单的 frontmatter 提取（不依赖外部包）
const extractAndStripFrontmatter = (content) => {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { frontmatter: {}, content };

  const frontmatterStr = match[1];
  const body = match[2];
  const frontmatter = {};

  for (const line of frontmatterStr.split('\n')) {
    const colonIdx = line.indexOf(':');
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim();
      const value = line.slice(colonIdx + 1).trim().replace(/^["']|["']$/g, '');
      frontmatter[key] = value;
    }
  }

  return { frontmatter, content: body };
};

// 模块级缓存，避免每次 agent 步骤重复读取文件
let _bootstrapCache = undefined;

export const FuxianPlugin = async ({ client, directory }) => {
  const fuxianSkillsDir = path.resolve(__dirname, '../../skills');

  // 获取引导内容（首次调用后缓存）
  const getBootstrapContent = () => {
    if (_bootstrapCache !== undefined) return _bootstrapCache;

    const skillPath = path.join(fuxianSkillsDir, 'using-fuxian', 'SKILL.md');
    if (!fs.existsSync(skillPath)) {
      _bootstrapCache = null;
      return null;
    }

    const fullContent = fs.readFileSync(skillPath, 'utf8');
    const { content } = extractAndStripFrontmatter(fullContent);

    const toolMapping = `**OpenCode 工具映射：**
当技能引用你缺少的工具时，使用 opencode 等价物：
- \`TodoWrite\` → \`todowrite\`
- \`Task\` 工具（子代理）→ opencode 子代理系统（@mention）
- \`Skill\` 工具 → opencode 原生 \`skill\` 工具
- \`Read\`, \`Write\`, \`Edit\`, \`Bash\` → opencode 原生工具

使用 opencode 原生 \`skill\` 工具来列出和加载技能。`;

    _bootstrapCache = `<EXTREMELY_IMPORTANT>
You have fuxian.

**重要：using-fuxian 技能内容已在下方包含。它已经被加载——你正在遵循它。不要再次使用 skill 工具加载 "using-fuxian"——那会是冗余的。**

${content}

${toolMapping}
</EXTREMELY_IMPORTANT>`;

    return _bootstrapCache;
  };

  return {
    // 将技能路径注入 opencode 配置，自动发现技能
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(fuxianSkillsDir)) {
        config.skills.paths.push(fuxianSkillsDir);
      }
    },

    // 在会话第一条用户消息中注入引导上下文
    'experimental.chat.messages.transform': async (_input, output) => {
      const bootstrap = getBootstrapContent();
      if (!bootstrap || !output.messages.length) return;
      const firstUser = output.messages.find(m => m.info.role === 'user');
      if (!firstUser || !firstUser.parts.length) return;

      // 防止重复注入
      if (firstUser.parts.some(p => p.type === 'text' && p.text.includes('EXTREMELY_IMPORTANT'))) return;

      const ref = firstUser.parts[0];
      firstUser.parts.unshift({ ...ref, type: 'text', text: bootstrap });
    }
  };
};
