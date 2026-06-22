const ASSET_LIBRARY_RETURN_TO_KEY = "assetLibrary:returnTo";

export function rememberAssetLibraryReturnTo(pathname: string) {
  if (pathname.startsWith("/app/")) {
    sessionStorage.setItem(ASSET_LIBRARY_RETURN_TO_KEY, pathname);
  }
}

export function takeAssetLibraryReturnTo(): string | null {
  const returnTo = sessionStorage.getItem(ASSET_LIBRARY_RETURN_TO_KEY);
  sessionStorage.removeItem(ASSET_LIBRARY_RETURN_TO_KEY);
  return returnTo;
}
