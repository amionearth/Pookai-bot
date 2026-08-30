#pragma once
#include <ArduinoJson.h>

// ── Command types ─────────────────────────────────────────────────────────────

enum class CmdType {
    DRIVE,
    CLEAN_START,
    TURRET_HOME,
    TURRET_MOVE,
    PEN,
    ESTOP,
    UNKNOWN
};

enum class CleanMode { PRE, POST_NO_EXCLUDE, WET, UNKNOWN };
enum class PenState  { UP, DOWN, UNKNOWN };

struct DriveCmd      { int left; int right; int duration_ms; };
struct CleanStartCmd { CleanMode mode; };
struct TurretMoveCmd { float theta; float r; };
struct PenCmd        { PenState state; };

struct Command {
    CmdType type = CmdType::UNKNOWN;
    union {
        DriveCmd      drive;
        CleanStartCmd clean;
        TurretMoveCmd turret;
        PenCmd        pen;
    };
};

// ── Status struct (ESP32 → Pi) ────────────────────────────────────────────────

struct StatusUpdate {
    bool  ok           = true;
    char  phase[32]    = "idle";
    float turret_theta = 0.0f;
    float turret_r     = 0.0f;
    int   battery_mv   = 0;
    bool  obstacle     = false;
};

// ── Parsing helpers ───────────────────────────────────────────────────────────

inline CleanMode parseCleanMode(const char* s) {
    if (!s) return CleanMode::UNKNOWN;
    if (strcmp(s, "pre")             == 0) return CleanMode::PRE;
    if (strcmp(s, "post_no_exclude") == 0) return CleanMode::POST_NO_EXCLUDE;
    if (strcmp(s, "wet")             == 0) return CleanMode::WET;
    return CleanMode::UNKNOWN;
}

inline PenState parsePenState(const char* s) {
    if (!s) return PenState::UNKNOWN;
    if (strcmp(s, "up")   == 0) return PenState::UP;
    if (strcmp(s, "down") == 0) return PenState::DOWN;
    return PenState::UNKNOWN;
}

// Returns false if JSON is malformed or cmd field is missing.
inline bool parseCommand(const char* line, Command& out) {
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, line) != DeserializationError::Ok) return false;

    const char* cmd = doc["cmd"] | "";

    if (strcmp(cmd, "drive") == 0) {
        out.type          = CmdType::DRIVE;
        out.drive.left    = doc["left"]        | 0;
        out.drive.right   = doc["right"]       | 0;
        out.drive.duration_ms = doc["duration_ms"] | 0;
    } else if (strcmp(cmd, "clean_start") == 0) {
        out.type       = CmdType::CLEAN_START;
        out.clean.mode = parseCleanMode(doc["mode"] | "");
    } else if (strcmp(cmd, "turret_home") == 0) {
        out.type = CmdType::TURRET_HOME;
    } else if (strcmp(cmd, "turret_move") == 0) {
        out.type         = CmdType::TURRET_MOVE;
        out.turret.theta = doc["theta"] | 0.0f;
        out.turret.r     = doc["r"]     | 0.0f;
    } else if (strcmp(cmd, "pen") == 0) {
        out.type      = CmdType::PEN;
        out.pen.state = parsePenState(doc["state"] | "");
    } else if (strcmp(cmd, "estop") == 0) {
        out.type = CmdType::ESTOP;
    } else {
        out.type = CmdType::UNKNOWN;
    }
    return true;
}

// Serialize and print a StatusUpdate to Serial as a JSON line.
inline void sendStatus(const StatusUpdate& s) {
    StaticJsonDocument<256> doc;
    doc["status"]       = s.ok ? "ok" : "error";
    doc["phase"]        = s.phase;
    doc["turret_theta"] = s.turret_theta;
    doc["turret_r"]     = s.turret_r;
    doc["battery_mv"]   = s.battery_mv;
    doc["obstacle"]     = s.obstacle;
    serializeJson(doc, Serial);
    Serial.println();
}
