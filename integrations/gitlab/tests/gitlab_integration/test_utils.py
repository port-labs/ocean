import pytest
from gitlab_integration.core.utils import _match, does_pattern_apply, generate_ref

def test_basic_exact_matches():
    """Test exact path matching without any glob patterns"""
    assert does_pattern_apply("a/b", "a/b")
    assert does_pattern_apply("team/service", "team/service")
    assert not does_pattern_apply("a/b", "a/c")

def test_parent_directory_matching():
    """Test matching parent directories with ** pattern.
    This is critical for GitLab group token mapping."""
    # Parent directory should match with **
    assert does_pattern_apply("team/**", "team"), "Parent directory should match with **"
    assert does_pattern_apply("org/**", "org"), "Parent org should match with **"
    
    # Should also match subdirectories with same pattern
    assert does_pattern_apply("team/**", "team/service")
    assert does_pattern_apply("team/**", "team/project/service")

def test_recursive_matching():
    """Test GitLab's recursive directory matching with **"""
    # Match service at any depth
    assert does_pattern_apply("**/service", "service")
    assert does_pattern_apply("**/service", "team/service")
    assert does_pattern_apply("**/service", "org/team/service")
    
    # Shouldn't match partial names
    assert not does_pattern_apply("**/service", "microservice")
    assert not does_pattern_apply("**/service", "team/microservice")

def test_multiple_patterns():
    patterns = ["**/DevopsTeam/*Service", "**/RnDTeam/*Service"]
    
    # Should match DevopsTeam services
    assert does_pattern_apply(patterns, "DevopsTeam/UserService")
    assert does_pattern_apply(patterns, "org/DevopsTeam/AuthService")
    
    # Should match RnDTeam services
    assert does_pattern_apply(patterns, "RnDTeam/DataService")
    assert does_pattern_apply(patterns, "org/RnDTeam/ApiService")
    
    # Should not match other teams or non-service projects
    assert not does_pattern_apply(patterns, "DevopsTeam/UserApp")
    assert not does_pattern_apply(patterns, "QATeam/TestService")

@pytest.mark.parametrize("pattern,path,should_match", [
    # Basic matches
    ("a/b", "a/b", True),
    ("a/b", "a/c", False),
    
    # Parent directory matches
    ("team/**", "team", True),
    ("team/**", "team/service", True),
    ("team/**", "team/project/service", True),
    ("team/**", "other/team/service", False),
    
    # Recursive directory matches
    ("**/service", "service", True),
    ("**/service", "team/service", True),
    ("**/service", "org/team/service", True),
    ("**/service", "service/team", False),
    
    # Complex patterns from real usage
    ("org/**/service", "org/service", True),
    ("org/**/service", "org/team/service", True),
    ("org/**/service", "org/team/project/service", True),
    ("org/**/service", "other/org/service", False),
])
def test_gitlab_token_mapping_patterns(pattern, path, should_match):
    """Test patterns in the context of GitLab token mapping"""
    assert does_pattern_apply(pattern, path) == should_match, \
        f"Pattern '{pattern}' {'should' if should_match else 'should not'} match path '{path}'"
