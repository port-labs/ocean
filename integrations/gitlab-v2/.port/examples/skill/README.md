# Example mapping (not applied by default — add to your GitLab v2 mapping to enable)
#
# resources:
#   - kind: skill
#     selector:
#       query: 'true'
#       content: skill.md
#     port:
#       entity:
#         mappings:
#           identifier: .repository.path_with_namespace + "/" + .skill.name
#           title: .skill.name
#           blueprint: '"skill"'
#           properties:
#             description: .skill.description
#             instructions: .skill.instructions
#             path: .skill.skillMdPath
#             repo: .repository.path_with_namespace
#
#   - kind: plugin
#     selector:
#       query: 'true'
#     port:
#       entity:
#         mappings:
#           identifier: .repository.path
#           title: .plugin.displayName // .plugin.name
#           blueprint: '"plugin"'
#           properties:
#             description: .plugin.description
#             url: .repository.web_url
#             supportsClaudeCode: .plugin.supports.claude
#             supportsCursor: .plugin.supports.cursor
#             supportsCodex: .plugin.supports.codex
#             supportsAgents: .plugin.supports.agents
#             supportsKimi: .plugin.supports.kimi
#             supportsOpenCode: .plugin.supports.opencode
#             supportsPi: .plugin.supports.pi
#             supportsAntigravity: .plugin.supports.antigravity
