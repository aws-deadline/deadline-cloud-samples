internal_package_remove_from_search_path () {
    # Removes the given path from the given environment variable.
    # Usage: internal_package_remove_from_search_path VAR_NAME /search/path/value
    eval "CURRENT_VALUE=\$$1"
    if [ "$CURRENT_VALUE" = "$2" ]; then
        eval "unset $1"
    else
        NEW_VALUE="$(echo ":$CURRENT_VALUE:" | sed -e "s|:$2:|:|")"
        NEW_VALUE="${NEW_VALUE%:}"
        NEW_VALUE="${NEW_VALUE#:}"
        eval "export \"$1=\$NEW_VALUE\""
    fi
}

internal_package_remove_from_search_path PXR_PLUGINPATH_NAME "$REDSHIFT_COREDATAPATH/redshift4solaris/$RS_PLUGIN_VERSION"

unset REDSHIFT_COREDATAPATH
unset REDSHIFT_LOCALDATAPATH
unset REDSHIFT_PROCEDURALSPATH
unset REDSHIFT_PREFSPATH
unset HOUDINI_DSO_ERROR
unset -f internal_package_remove_from_search_path
