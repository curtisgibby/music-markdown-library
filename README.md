# music-markdown-library

A collection of song chord charts formatted for [Music Markdown](https://github.com/music-markdown/music-markdown).

## How to Use

1. Go to [Music Markdown](https://musicmd.app)
2. Click on the **+** button at the bottom right
3. In the **Add Repository** dialog box, fill in:
   - **Repository Owner**: `curtisgibby`
   - **Repository Name**: `music-markdown-library`
4. Browse and select any song to view with chords aligned above lyrics

## File Naming

Song files are named `{artistName} - {songTitle}.md` so they sort by artist.

## Title-Based Symlinks

To make songs browsable by title as well, each song has a companion symlink named
`-{songTitle} - {artistName}.md` (note the leading dash). The leading dash sorts
these title-first entries to the top of the file list, keeping them grouped
separately from the artist-first song files.

Create one for a new song like this:

```bash
ln -s "{artistName} - {songTitle}.md" "-{songTitle} - {artistName}.md"
```

For example, for `The Youngbloods - Let's Get Together.md`:

```bash
ln -s "The Youngbloods - Let's Get Together.md" "-Let's Get Together - The Youngbloods.md"
```
