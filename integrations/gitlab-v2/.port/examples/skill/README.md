# Example mapping (not applied by default — add to your GitLab v2 Ocean mapping to enable)
#
# Validated mapping fragment (ready to append): see `mapping.yml` in this folder.
#
# Blueprints (created in Port): `skill`, `agentPlugin`
# Relation: skill → agentPlugin (many skills per plugin repo)
# Note: blueprint id is `agentPlugin` (not `plugin`) to avoid Port's /plugins UI route.
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
#             root: .skill.root
#             repo: .repository.path_with_namespace
#             repoUrl: .repository.web_url
#             branch: .branch
#             source: '"gitlab"'
#           relations:
#             plugin: .repository.path_with_namespace
#
#   - kind: plugin
#     selector:
#       query: 'true'
#     port:
#       entity:
#         mappings:
#           identifier: .repository.path_with_namespace
#           title: .plugin.displayName // .plugin.name
#           blueprint: '"plugin"'
#           properties:
#             description: .plugin.description
#             version: .plugin.version
#             url: .repository.web_url
#             repo: .repository.path_with_namespace
#             source: '"gitlab"'
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
