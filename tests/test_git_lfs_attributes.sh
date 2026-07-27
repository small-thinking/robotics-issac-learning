#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

IMAGE_EXTENSIONS=(
  png jpg jpeg jpe jfif gif webp bmp tga tif tiff heic heif avif ico
  jp2 j2k jpf jpx exr hdr dds ktx ktx2 qoi svgz psd xcf
  pbm pgm ppm pnm dng cr2 cr3 nef arw raf orf rw2
)

assert_attr() {
  local path="$1"
  local attribute="$2"
  local expected_value="$3"
  local actual
  local expected

  actual="$(git check-attr "${attribute}" -- "${path}")"
  expected="${path}: ${attribute}: ${expected_value}"
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'attribute mismatch: expected "%s", got "%s"\n' \
      "${expected}" "${actual}" >&2
    return 1
  fi
}

for extension in "${IMAGE_EXTENSIONS[@]}"; do
  for candidate in "${extension}" "$(printf '%s' "${extension}" | tr '[:lower:]' '[:upper:]')"; do
    probe="lfs-attribute-probe.${candidate}"
    assert_attr "${probe}" filter lfs
    assert_attr "${probe}" diff lfs
    assert_attr "${probe}" merge lfs
    assert_attr "${probe}" text unset
  done
done

assert_attr "lfs-attribute-probe.svg" filter unspecified
assert_attr "lfs-attribute-probe.svg" diff unspecified
assert_attr "lfs-attribute-probe.svg" merge unspecified
assert_attr "lfs-attribute-probe.svg" text set

printf 'Git LFS image attribute checks passed.\n'
