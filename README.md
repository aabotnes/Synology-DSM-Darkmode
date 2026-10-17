# Dark Mode for Synology DSM

A Package Center package that gives the DSM 7 web interface a dark theme. Start or stop the package to turn dark mode on or off.

## Install

1. Download the latest `DarkMode-x.y.z.spk` from [Releases](https://github.com/aabotnes/Synology-DSM-Darkmode/releases/latest).
2. In DSM, open **Package Center**, click **Manual Install**, choose the file and click **Next**.
   If DSM warns that the package is from an unknown publisher, click **Yes** to continue.
3. Pick whether DSM should always be dark or follow your computer's light/dark setting.
4. Do the one-time setup below, which the wizard also shows you.

### One-time setup

DSM 7 doesn't let third-party packages change system files, so dark mode needs one task that runs as root. It also brings dark mode back after DSM updates, which overwrite DSM's stylesheets.

1. Open **Control Panel > Task Scheduler**.
2. Click **Create > Triggered Task > User-defined script**.
3. Name it **Dark Mode**, set User to **root** and Event to **Boot-up**.
4. On the **Task Settings** tab, paste this into Run command:

   ```
   /var/packages/DarkMode/target/bin/darkmode apply
   ```

5. Click **OK**, select the task and click **Run** once.
6. Reload DSM in your browser.

If you'd rather use SSH, `sudo /var/packages/DarkMode/target/bin/darkmode apply` does the same thing once, but won't reapply after a DSM update.

The **Dark Mode** app in the DSM main menu shows whether the theme is on and whether setup has run.

## Turn it off or remove it

- **Off for now:** stop the package in Package Center and reload DSM. Start it again to switch back.
- **Remove completely:** change the task's Run command to `/var/packages/DarkMode/target/bin/darkmode revert`, run it once, delete the task, then uninstall the package.
  If you uninstall first, nothing breaks: DSM just keeps one harmless line pointing at a file that no longer exists until the next DSM update replaces it.

## How it works

- `darkmode apply` adds one line at the top of `/usr/syno/synoman/webman/resources/css/desktop.css` that imports `/webman/3rdparty/DarkMode/dark.css`, and rebuilds the `.gz` copy nginx serves. It keeps a copy of the original in `/var/packages/DarkMode/var/backup/`. Running it again does nothing.
- `darkmode revert` removes exactly that line.
- The package serves `dark.css` itself. Starting the package fills it with the theme and stopping it empties it, so switching needs no root.
- `darkmode apply` also builds the theme from your NAS's own stylesheets (DSM and every installed package): each rule that sets a light background, dark text or light border gets a dark-mode twin, the way Dark Reader works, but done once on the NAS. Images, icons and wallpapers are left alone. It uses the Python 3 that ships with DSM 7; without it, only the hand-written base theme in `src/package/share/dark.css` is used.
- After installing or updating other packages, run the Dark Mode task once (or reboot) so their screens are included.
- Some base selectors come from [danslabs/synology-dsm-dark-mode](https://github.com/danslabs/synology-dsm-dark-mode) (MIT, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

Tested against a simulated DSM file layout (`tools/test.sh`); it has not been run on real hardware yet, so please open an issue with your DSM version if something looks off.

## Build

```
tools/test.sh     # run the script tests
tools/build.sh    # writes dist/DarkMode-<VERSION>.spk
```

Every push to `main` runs the tests and builds the package. When `VERSION` holds a version that hasn't been released yet, it is published as a GitHub release.
