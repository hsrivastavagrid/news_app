const PREFIX = "[NewsPulse]";

function stamp(level, args) {
  const time = new Date().toISOString();
  return [`${PREFIX} ${time} ${level}`, ...args];
}

export const log = {
  info: (...args) => console.info(...stamp("INFO", args)),
  warn: (...args) => console.warn(...stamp("WARN", args)),
  error: (...args) => console.error(...stamp("ERROR", args)),
};
