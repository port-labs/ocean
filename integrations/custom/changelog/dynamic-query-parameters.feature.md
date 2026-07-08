Added support for `selector.query_parameters` in the custom integration so query parameter values can be discovered from API endpoints during resync.
This includes Cartesian request expansion for multi-value discoveries and precedence where dynamic values override static `selector.query_params`.
