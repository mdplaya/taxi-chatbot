def add_resource_fields(ctx: dict, os: str, use_type: str) -> dict:
    """Convenience helper to simulate Compute outputs by adding resource fields.
    Modifies a copy of ctx to include os/useType in extracted_requirements.
    """
    new_ctx = dict(ctx)
    er = dict(new_ctx.get('extracted_requirements', {}))
    if os:
        er['os'] = os
    if use_type:
        er['useType'] = use_type
    new_ctx['extracted_requirements'] = er
    return new_ctx

