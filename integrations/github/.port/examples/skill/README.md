# Example mapping (not applied by default — add to your GitHub Ocean mapping to enable)
#
# Validated mapping fragment (ready to append): see `mapping.yml` in this folder.
#
# Blueprints (created in Port): `skill`, `plugin`
# Relation: skill → plugin (many skills per plugin repo)
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
#             root: .skill.root
#             repo: .repository.full_name
#             repoUrl: .repository.html_url
#             branch: .branch
#             source: '"github"'
#           relations:
#             plugin: .repository.full_name
#
#   - kind: plugin
#     selector:
#       query: 'true'
#     port:
#       entity:
#         mappings:
#           identifier: .repository.full_name
#           title: .plugin.displayName // .plugin.name
#           blueprint: '"plugin"'
#           properties:
#             description: .plugin.description
#             version: .plugin.version
#             url: .repository.html_url
#             repo: .repository.full_name
#             source: '"github"'
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
