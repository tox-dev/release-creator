Reject ``additional_dependencies`` on a hook whose language, set in the configuration or in the hook repository's
manifest, is not Python, because those dependencies would install unpinned and uncooled.
