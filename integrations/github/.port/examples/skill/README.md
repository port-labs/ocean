# Example mapping (not applied by default — add to your GitHub Ocean mapping to enable)
#
# resources:
#   - kind: skill
#     selector:
#       query: 'true'
#       content: skill.md
#     port:
#       entity:
#         mappings:
#           identifier: .repository.full_name + "/" + .skill.name
#           title: .skill.name
#           blueprint: '"skill"'
#           properties:
#             description: .skill.description
#             instructions: .skill.instructions
#             path: .skill.skillMdPath
#             repo: .repository.full_name
#
#   - kind: plugin
#     selector:
#       query: 'true'
#     port:
#       entity:
#         mappings:
#           identifier: .repository.name
#           title: .plugin.displayName // .plugin.name
#           blueprint: '"plugin"'
#           properties:
#             description: .plugin.description
#             url: .repository.html_url
#             supportsClaudeCode: .plugin.supports.claude
#             supportsCursor: .plugin.supports.cursor
#             supportsCodex: .plugin.supports.codex
#             supportsAgents: .plugin.supports.agents
#             supportsKimi: .plugin.supports.kimi
#             supportsOpenCode: .plugin.supports.opencode
#             supportsPi: .plugin.supports.pi
#             supportsAntigravity: .plugin.supports.antigravity
#             claudeMarketplace: .plugin.claude.marketplaceName
#             claudePlugin: .plugin.claude.name
