--[[
Site filter for pages written as GitHub READMEs.

1. Title: when a page has no `title`, its first level-1 heading becomes the
   title (and is removed from the body so it is not shown twice).
2. Links: relative links are checked against what the site renders.
   * analyses/<name>/README.md  -> that analysis's site page (index.qmd)
   * other rendered pages, figures and anchors are left alone
   * anything else (root README, code, results, tests, archive) points to
     the file on GitHub, so no link on the site is dead.
]]

local REPO = "https://github.com/danae1968/tennis_database/blob/main/"

local function split(path)
  local parts = {}
  for p in path:gmatch("[^/]+") do table.insert(parts, p) end
  return parts
end

-- Normalise a repo-relative path made of a directory plus a relative href.
local function resolve(dir, href)
  local out = {}
  for _, p in ipairs(split(dir)) do table.insert(out, p) end
  for _, p in ipairs(split(href)) do
    if p == ".." then
      if #out == 0 then return nil end
      table.remove(out)
    elseif p ~= "." then
      table.insert(out, p)
    end
  end
  return table.concat(out, "/")
end

local function input_dir()
  local file = quarto.doc.input_file:gsub("\\", "/")
  local root = (quarto.project.directory or ""):gsub("\\", "/")
  local rel = file
  if root ~= "" and file:sub(1, #root) == root then
    rel = file:sub(#root + 2)
  end
  return rel:match("^(.*)/[^/]*$") or ""
end

local function is_site_path(p)
  return p == "index.qmd"
    or p:match("^about/[^/]+%.qmd$")
    or p:match("^analyses/[^/]+/index%.qmd$")
    or p:match("^analyses/[^/]+/METHODS%.md$")
    or p:match("^analyses/reviews/[^/]+%.q?md$")
    or p:match("^analyses/[^/]+/figures/")
end

local dir

function Link(el)
  local href = el.target
  if href:match("^%a[%w+.-]*:") or href:match("^#") or href:match("^/") then
    return nil -- absolute URL, mailto, in-page anchor or site-absolute path
  end
  local path, frag = href:match("^([^#]*)(#?.*)$")
  if path == "" then return nil end
  dir = dir or input_dir()
  local p = resolve(dir, path)
  if p == nil then return nil end
  if p:match("^analyses/[^/]+/README%.md$") then
    el.target = path:gsub("README%.md$", "index.qmd") .. frag
  elseif not is_site_path(p) then
    el.target = REPO .. p .. frag
  end
  return el
end

function Pandoc(doc)
  if doc.meta.title == nil then
    for i, blk in ipairs(doc.blocks) do
      if blk.t == "Header" and blk.level == 1 then
        doc.meta.title = pandoc.MetaInlines(blk.content)
        doc.meta.pagetitle = pandoc.utils.stringify(blk.content)
        doc.blocks:remove(i)
        break
      elseif blk.t ~= "RawBlock" then
        break
      end
    end
  end
  return doc
end
