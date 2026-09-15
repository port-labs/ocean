REACTION_CREATE = """
mutation ReactionCreate($input: ReactionCreateInput!) {
    reactionCreate(input: $input) {
        success
        reaction {
            id
            emoji
        }
    }
}
"""
