use base64::Engine;
use serde_json::Value;
use std::hash::{DefaultHasher, Hash, Hasher};
use std::path::PathBuf;

const MAX_BYTES: usize = 2 * 1024 * 1024;

#[derive(Default)]
pub struct Artwork {
    source: String,
    path: Option<PathBuf>,
}

impl Artwork {
    pub fn resolve(&mut self, tab: i64, msg: &mut Value) {
        let Some(source) = msg.get("artUrl").and_then(Value::as_str).map(str::to_owned) else {
            return;
        };
        if self.source != source {
            self.clear();
            self.source = source.clone();
        }
        if let Some(encoded) = msg.get("artData").and_then(Value::as_str) {
            if encoded.len() <= MAX_BYTES.div_ceil(3) * 4 {
                if let Ok(data) = base64::engine::general_purpose::STANDARD.decode(encoded) {
                    // Cache image bytes only, never a caller-supplied filename or arbitrary file contents.
                    let image = data.starts_with(b"\xff\xd8\xff")
                        || data.starts_with(b"\x89PNG\r\n\x1a\n")
                        || (data.starts_with(b"RIFF") && data.get(8..12) == Some(b"WEBP"))
                        || data.starts_with(b"GIF87a")
                        || data.starts_with(b"GIF89a");
                    if image && data.len() <= MAX_BYTES {
                        let mut hash = DefaultHasher::new();
                        data.hash(&mut hash);
                        let dir = std::env::temp_dir()
                            .join(format!("mpris-tab-bridge-art-{}", std::process::id()));
                        let path = dir.join(format!("{tab}-{:x}.img", hash.finish()));
                        if std::fs::create_dir_all(&dir).is_ok() {
                            #[cfg(unix)]
                            {
                                use std::os::unix::fs::PermissionsExt;
                                let _ = std::fs::set_permissions(
                                    &dir,
                                    std::fs::Permissions::from_mode(0o700),
                                );
                            }
                            if std::fs::write(&path, data).is_ok() {
                                if self.path.as_ref() != Some(&path) {
                                    self.remove_file();
                                }
                                self.path = Some(path);
                            }
                        }
                    }
                }
            }
        }
        if let Some(object) = msg.as_object_mut() {
            object.remove("artData");
        }
        if let Some(path) = &self.path {
            // Encode spaces/non-ASCII bytes in the local file URI.
            use std::os::unix::ffi::OsStrExt;
            let mut uri = String::from("file://");
            for byte in path.as_os_str().as_bytes() {
                if byte.is_ascii_alphanumeric() || b"/._-".contains(byte) {
                    uri.push(*byte as char);
                } else {
                    uri.push_str(&format!("%{byte:02X}"));
                }
            }
            msg["artUrl"] = Value::String(uri);
        }
    }
    fn remove_file(&mut self) {
        if let Some(path) = self.path.take() {
            let _ = std::fs::remove_file(path);
        }
    }
    fn clear(&mut self) {
        self.remove_file();
    }
}
impl Drop for Artwork {
    fn drop(&mut self) {
        self.clear();
    }
}
