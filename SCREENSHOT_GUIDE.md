# Screenshot Guide for Eddie

This guide will help you create compelling screenshots for the GitHub repository.

## 📸 Recommended Screenshots

### 1. **Architecture Diagrams** ✅ DONE
The Mermaid diagrams in the README will automatically render on GitHub, showing:
- System architecture
- MQTT message flow

### 2. **Terminal Output - Voice Processing**

**What to capture:**
Run Eddie and capture the terminal showing:
- Voice transcription from Whisper
- NLP entity extraction
- Intent classification
- MQTT message publishing

**How to capture:**
```bash
# Start Eddie with verbose output
python translate.py

# Speak a command like "Play Radio by Alkaline Trio"
# Screenshot the terminal output showing:
# - "Transcribed: Play Radio by Alkaline Trio"
# - Entity extraction: band="Alkaline Trio", song="Radio"
# - Category: "music"
```

**Suggested filename:** `images/terminal-voice-processing.png`

### 3. **Terminal Output - Action Execution**

**What to capture:**
The Action Layer terminal showing command execution

**How to capture:**
```bash
# In a separate terminal
python action.py

# After speaking a command, screenshot showing:
# - Received action from MQTT
# - Tool selection (e.g., "executing music_manager")
# - API call to Spotify
# - Success response
```

**Suggested filename:** `images/terminal-action-execution.png`

### 4. **Configuration File Example**

**What to capture:**
A clean view of the `.env.example` file to show users how easy setup is

**How to do it:**
```bash
# Open .env.example in your editor
# Screenshot showing the configuration structure
# Make sure it's well-formatted and easy to read
```

**Suggested filename:** `images/config-example.png`

### 5. **MQTT Message Inspector** (Optional but impressive)

**What to capture:**
Use an MQTT client like MQTT Explorer or mosquitto_sub to show live messages

**How to do it:**
```bash
# Install MQTT Explorer (GUI) or use mosquitto_sub
mosquitto_sub -h localhost -t '#' -v

# Speak a command and screenshot the message flow:
# - mic/mbp (audio data)
# - step-one/action (parsed command)
# - vits/in (response text)
```

**Suggested filename:** `images/mqtt-messages.png`

### 6. **Spotify Integration** (Optional)

**What to capture:**
Spotify desktop app showing a song playing via Eddie

**How to do it:**
- Speak "Play [song name]"
- Screenshot Spotify app with the song playing
- Add annotation: "Controlled by Eddie voice command"

**Suggested filename:** `images/spotify-integration.png`

## 🎨 Screenshot Best Practices

### Terminal Screenshots
1. **Use a clean terminal theme** (dark background with good contrast)
2. **Increase font size** for readability (14-16pt)
3. **Clear any sensitive information** (paths, IP addresses if needed)
4. **Trim to relevant content** (don't show empty space)
5. **Use a terminal with good colors** (iTerm2, Hyper, Windows Terminal)

### File/Code Screenshots
1. **Use syntax highlighting** (VS Code, Sublime, etc.)
2. **Show line numbers** for reference
3. **Zoom in** so text is clearly readable
4. **Use a popular theme** (GitHub Dark, Dracula, One Dark)

### Composition
1. **Crop tightly** around relevant content
2. **Add subtle arrows or highlights** if needed (use Preview, Snagit, or Gimp)
3. **Keep it simple** - one concept per screenshot
4. **Use consistent sizing** across screenshots

## 📐 Recommended Dimensions

- **Full terminal:** 1200x800px or 1600x1000px
- **Code snippets:** 1000x600px
- **Banner/header:** 1280x640px (2:1 ratio)

## 🛠️ Tools for Capturing

### macOS
- Built-in: `Cmd + Shift + 4` (select area)
- Built-in: `Cmd + Shift + 5` (options)
- Preview for editing/cropping

### Linux
- GNOME Screenshot
- Flameshot (excellent for annotations)
- Shutter

### Windows
- Snipping Tool
- `Win + Shift + S`
- ShareX (advanced, free)

## 📝 Adding Screenshots to README

Once you have screenshots, add them to the README:

```markdown
## Screenshots

### Voice Processing in Action
![Voice Processing](images/terminal-voice-processing.png)

### MQTT Message Flow
![MQTT Messages](images/mqtt-messages.png)

### Easy Configuration
![Configuration](images/config-example.png)
```

## 🎯 Priority Screenshots

If you can only create a few, prioritize these:

1. **Terminal output showing voice → text → action** (Most important)
2. **Config file example** (Shows ease of setup)
3. **MQTT messages** (Shows the architecture in action)

## 💡 Pro Tips

1. **Anonymize before sharing:**
   - Replace real IPs with `192.168.1.x`
   - Replace usernames with `user` or leave generic
   - No real API keys (they should be in .env anyway!)

2. **Show personality:**
   - Use fun voice commands in examples
   - Show variety (music, timers, weather)
   - Demonstrate the "wow" factor

3. **Keep it real:**
   - Don't fake output
   - Show actual terminal sessions
   - Include minor imperfections (more authentic)

## 🚀 Next Steps

After creating screenshots:

1. Save them in the `images/` directory
2. Update README.md to include them
3. Commit and push to GitHub
4. GitHub will display them automatically!

```bash
git add images/
git commit -m "Add screenshots demonstrating Eddie's features"
git push
```

---

**Remember:** Good screenshots can make the difference between someone trying your project or scrolling past it!
