{ pkgs, ... }: {
  channel = "stable-24.11";
  packages = [
    pkgs.python3
    pkgs.nodejs_20
  ];
  idx = {
    extensions = [
      "vscode-styled-components"
    ];
    previews = {
      enable = true;
    };
  };
}