import os
import re
import yaml
from typing import Union

from yaml import SafeLoader, UnsafeLoader, CBaseLoader, CFullLoader, ScalarNode
    

def yaml_env_setup(
    loader: Union[SafeLoader, UnsafeLoader, CBaseLoader, CFullLoader]
    ) -> Union[SafeLoader, UnsafeLoader, CBaseLoader, CFullLoader]:
    
    match_pattern = r'\$\{[a-zA-Z0-9_]+\}'
    env_matcher = re.compile(match_pattern)
    
    def env_constructor(
        loader: Union[SafeLoader, UnsafeLoader, CBaseLoader, CFullLoader], node: ScalarNode
        ) -> str:
        
        value = node.value
        env_matches = env_matcher.findall(value)
        for match in env_matches:
            match_name = match[2:-1]
            sub_pattern = match_pattern[:4] + match_name + match_pattern[-2:]
            value = re.sub(sub_pattern, os.environ[match[2:-1]], value)
        
        return value
        
    
    yaml.add_implicit_resolver(r"$", env_matcher, Loader=SafeLoader)
    yaml.add_constructor(r"$", env_constructor, Loader=SafeLoader)
    
    return loader
