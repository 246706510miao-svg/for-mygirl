import confetti from "canvas-confetti";

// 这个函数用于签到、保存记录和兑换奖品后的轻量庆祝反馈。
export function celebrate() {
  void confetti({
    particleCount: 48,
    spread: 64,
    startVelocity: 28,
    scalar: 0.82,
    ticks: 140,
    origin: { y: 0.78 },
    colors: ["#4fc0d9", "#b18ace", "#ffffff"]
  });
}
