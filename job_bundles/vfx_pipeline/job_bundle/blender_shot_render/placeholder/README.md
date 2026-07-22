# placeholder/

`shot.blend` exists only so the static template's `ShotAsset` PATH parameter has
a valid in-bundle default for `openjd check`/`summary`.

At real submission time the launcher (`studio-pipe submit`) overrides it with the
resolved shot asset, so this placeholder is never attached to an actual job. Only
`shot.blend` lives here. The DCC and plugin are not PATH parameters; they are
delivered as Conda packages by the Conda queue environment (see the bundle
README's "Software via Conda" section), so they need no placeholder here.
