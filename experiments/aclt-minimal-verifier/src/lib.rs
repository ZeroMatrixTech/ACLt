use std::{fs::File, io::Read};
pub const INPUT_LIMIT: u64 = 2_000_000;
pub const RESULT_LIMIT: u64 = 12_000_000;
pub fn read(path: &str, limit: u64) -> Result<String, String> {
    let mut text = String::new();
    File::open(path).map_err(|e| e.to_string())?.take(limit + 1)
        .read_to_string(&mut text).map_err(|e| e.to_string())?;
    if text.len() as u64 > limit { return Err("file too large".into()); }
    Ok(text)
}
pub fn number(s: &str) -> Result<i64, String> {
    let n = s.parse::<i64>().map_err(|_| "invalid integer")?;
    if n.to_string() != s { return Err("noncanonical integer".into()); }
    Ok(n)
}
pub fn fields(s: &str) -> Result<Vec<i64>, String> {
    s.split(|c: char| c == ' ' || ('\t'..='\r').contains(&c))
        .filter(|s| !s.is_empty()).map(number).collect()
}
pub fn input(path: &str) -> Result<Vec<i64>, String> {
    let values = fields(&read(path, INPUT_LIMIT)?)?;
    if values.is_empty() || values.len() > 100_000 || values.iter().any(|x| !(-1_000_000_000..=1_000_000_000).contains(x)) {
        return Err("input limit exceeded or empty input".into());
    }
    Ok(values)
}
pub fn chunk_size(s: &str) -> Result<usize, String> {
    let chunk = number(s)?;
    if !(1..=100_000).contains(&chunk) { return Err("chunk out of range".into()); }
    Ok(chunk as usize)
}
pub fn expected(values: &[i64], chunk: usize, id: usize) -> Vec<i64> {
    let start = id * chunk;
    let part = &values[start..std::cmp::min(start + chunk, values.len())];
    vec![id as i64, start as i64, part.len() as i64, part.iter().sum(),
        *part.iter().min().unwrap(), *part.iter().max().unwrap()]
}
pub fn verify(values: &[i64], chunk: usize, result: &str) -> Result<(), String> {
    let rows: Vec<_> = result.lines().collect();
    if rows.len() != values.len().div_ceil(chunk) { return Err("missing or extra chunks".into()); }
    for (id, row) in rows.iter().enumerate() {
        if fields(row)? != expected(values, chunk, id) {
            return Err(format!("chunk {id}: incorrect result, boundary, or order"));
        }
    }
    Ok(())
}
pub fn summary(values: &[i64], chunk: usize) -> String {
    format!("ACCEPT count={} chunks={} sum={} min={} max={}", values.len(), values.len().div_ceil(chunk),
        values.iter().sum::<i64>(), values.iter().min().unwrap(), values.iter().max().unwrap())
}
