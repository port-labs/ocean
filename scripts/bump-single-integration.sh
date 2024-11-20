#!/usr/bin/env bash
SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$(basename "$0")"
INTEGRATION_DIR="${SCRIPT_BASE}/../integrations"
INTEGRATION_TO_BUMP=""
TOWNCRIER_TYPES=( feature breaking deprecation improvement bugfix doc )

_usage() {
  echo -e "Usage :  ${SCRIPT_NAME} INTEGRATION_NAME
  Options:
    -h       Display this message
    -i       Integration
    -v       Optional explicit version (default to bumping minor)
"

}

_err() {
    echo -e "$1\n"
    _usage
    exit 1
}


_select_fragment_type_fzf(){
    printf "%s\n" "${TOWNCRIER_TYPES[@]}" | fzf -i --header="$@"
}

_select_fragment_type(){
    if [[ $(which fzf) ]]; then
        _select_fragment_type_fzf "$@"
        return
    fi
    PS3="Please enter change type: for $@:  "
    select opt in "${TOWNCRIER_TYPES[@]}"
    do
        case $opt in
            *)
                if [[ ${TOWNCRIER_TYPES[@]} =~ ${REPLY} ]]; then
                    echo "${REPLY}";
                    break;
                fi
                ;;
        esac
    done
}


while getopts "hi:v:" opt; do
  case ${opt} in
  h )
    _usage;
    exit 0
    ;;

  i )
    INTEGRATION_TO_BUMP="${OPTARG}"
    ;;

  v )
    EXPLICIT_VERSION_TO_BUMP="${OPTARG}"
    ;;

  * )
    _err "Option does not exist : ${OPTARG}";
    ;;
  esac
done
shift $((OPTIND -1))


if [[ -z ${INTEGRATION_TO_BUMP} ]]; then
    _err "Missing Integration to bump"
fi

CURRENT_INTEGRATION_DIR="${INTEGRATION_DIR}/${INTEGRATION_TO_BUMP}"

if [[ ! -d "${CURRENT_INTEGRATION_DIR}"  ]]; then
    _err "Invalid integration (${INTEGRATION_TO_BUMP}), it should be in the integrations directory"
fi

if [[ ! -f "${CURRENT_INTEGRATION_DIR}/pyproject.toml" ]]; then
    _err "${INTEGRATION_TO_BUMP} is missing a 'pyproject.toml' file"
fi


pushd ${CURRENT_INTEGRATION_DIR}
source .venv/bin/activate
CURRENT_VERSION=$(poetry version --short)

echo "Current version: ${CURRENT_VERSION}"
IFS='.' read -ra VERSION_COMPONENTS <<< "${CURRENT_VERSION}"

MAJOR_VERSION="${VERSION_COMPONENTS[0]}"
MINOR_VERSION="${VERSION_COMPONENTS[1]}"
PATCH_VERSION="${VERSION_COMPONENTS[2]}"

((PATCH_VERSION++))
NEW_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"
if [[ ! -z ${EXPLICIT_VERSION_TO_BUMP} ]]; then
    NEW_VERSION=${EXPLICIT_VERSION_TO_BUMP}
fi

poetry version "${NEW_VERSION}"
echo "New version: ${NEW_VERSION}"

echo "Gathering changelog for towncrier"
for COMMIT_SHA in $(git rev-list main...); do
    CURRENT_COMMIT=$(git log -1 --pretty="format:[%as] @%an - %B" ${COMMIT_SHA})
    CURRENT_TYPE=$(_select_fragment_type "${CURRENT_COMMIT}")
    towncrier create -c "${CURRENT_COMMIT}" --edit +random.${CURRENT_TYPE}
done

echo "Creating towncrier fragment"
echo "Run towncrier build to increment the patch version"
towncrier build --yes --version ${NEW_VERSION}
rm -rf ${CURRENT_INTEGRATION_DIR}/changelog/*
git add ${CURRENT_INTEGRATION_DIR}/pyproject.toml ${CURRENT_INTEGRATION_DIR}/CHANGELOG.md

echo "committing ${INTEGRATION_TO_BUMP} bump"
git commit -m "Bumped ${INTEGRATION_TO_BUMP} integration version from ${CURRENT_VERSION} to ${NEW_VERSION}"

popd
