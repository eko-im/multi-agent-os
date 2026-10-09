import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const REPOSITORY = "can1357/oh-my-pi";
const BUN_FIX_PR = 41086;
const OMP_STDIN_END_ISSUE = 8025;
const OMP_EINTR_ISSUE = 5328;
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;
const REQUEST_TIMEOUT_MS = 5_000;
const MINIMUM_EINTR_SAFE_BUN = "1.4.1";

export const DEFAULT_STATE_PATH = join(homedir(), ".omp", "agent", "state", "omp-upstream-watch.json");

export interface WatchState {
	schema: 1;
	checkedAt: string;
	bunVersion: string;
	bunEintrRetryShipped: boolean;
	ompMainSha: string;
	ompLatestTag: string;
	terminalSourceSha256: string;
	terminalRegressionSha256: string;
	stdinEndIssue: { state: string; updatedAt: string };
	eintrIssue: { state: string; updatedAt: string };
	bunFix: { state: string; mergedAt: string | null };
	permanentStatus: "UNRESOLVED";
}

interface FetchResponse {
	ok: boolean;
	status: number;
	json(): Promise<unknown>;
	text(): Promise<string>;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<FetchResponse>;

type OmpContext = {
	hasUI?: boolean;
	ui?: { notify(message: string, level?: "info" | "warning" | "error"): void };
};

type OmpExtensionApi = {
	on(event: "session_start", handler: (event: unknown, context: OmpContext) => void): void;
};

function numericVersion(version: string): [number, number, number] {
	const [major = "0", minor = "0", patch = "0"] = version.split(/[.-]/, 3);
	return [Number(major) || 0, Number(minor) || 0, Number(patch) || 0];
}

export function versionAtLeast(version: string, minimum: string): boolean {
	const actual = numericVersion(version);
	const expected = numericVersion(minimum);
	for (let index = 0; index < actual.length; index += 1) {
		if (actual[index] !== expected[index]) return actual[index] > expected[index];
	}
	return true;
}


async function request(fetchImpl: FetchLike, url: string): Promise<FetchResponse> {
	const response = await fetchImpl(url, {
		headers: { Accept: "application/vnd.github+json", "User-Agent": "omp-upstream-watch" },
		signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
	});
	if (!response.ok) throw new Error(`GitHub request failed (${response.status}) for ${url}`);
	return response;
}

async function jsonObject(fetchImpl: FetchLike, url: string): Promise<Record<string, unknown>> {
	const value = await (await request(fetchImpl, url)).json();
	if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Unexpected GitHub response for ${url}`);
	return value as Record<string, unknown>;
}

async function jsonArray(fetchImpl: FetchLike, url: string): Promise<Record<string, unknown>[]> {
	const value = await (await request(fetchImpl, url)).json();
	if (!Array.isArray(value)) throw new Error(`Unexpected GitHub response for ${url}`);
	return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}


function issueState(value: Record<string, unknown>): { state: string; updatedAt: string } {
	return {
		state: typeof value.state === "string" ? value.state : "unknown",
		updatedAt: typeof value.updated_at === "string" ? value.updated_at : "unknown",
	};
}

export async function collectUpstreamState(
	fetchImpl: FetchLike = fetch as FetchLike,
	bunVersion: string = Bun.version,
	now: Date = new Date(),
): Promise<WatchState> {
	const api = `https://api.github.com/repos/${REPOSITORY}`;
	const [main, tags, stdinEndIssue, eintrIssue, bunFix] = await Promise.all([
		jsonObject(fetchImpl, `${api}/commits/main`),
		jsonArray(fetchImpl, `${api}/tags?per_page=1`),
		jsonObject(fetchImpl, `${api}/issues/${OMP_STDIN_END_ISSUE}`),
		jsonObject(fetchImpl, `${api}/issues/${OMP_EINTR_ISSUE}`),
		jsonObject(fetchImpl, `https://api.github.com/repos/oven-sh/bun/pulls/${BUN_FIX_PR}`),
	]);
	const mainSha = typeof main.sha === "string" ? main.sha : "unknown";
	const latestTag = typeof tags[0]?.name === "string" ? tags[0].name : "unknown";
	const rawBase = `https://raw.githubusercontent.com/${REPOSITORY}/${encodeURIComponent(mainSha)}/packages/tui`;
	const [terminalSource, terminalRegression] = await Promise.all([
		(await request(fetchImpl, `${rawBase}/src/terminal.ts`)).text(),
		(await request(fetchImpl, `${rawBase}/test/terminal-disconnect-raw-mode-throw.test.ts`)).text(),
	]);

	return {
		schema: 1,
		checkedAt: now.toISOString(),
		bunVersion,
		bunEintrRetryShipped: versionAtLeast(bunVersion, MINIMUM_EINTR_SAFE_BUN),
		ompMainSha: mainSha,
		ompLatestTag: latestTag,
		terminalSourceSha256: createHash("sha256").update(terminalSource).digest("hex"),
		terminalRegressionSha256: createHash("sha256").update(terminalRegression).digest("hex"),
		stdinEndIssue: issueState(stdinEndIssue),
		eintrIssue: issueState(eintrIssue),
		bunFix: {
			state: typeof bunFix.state === "string" ? bunFix.state : "unknown",
			mergedAt: typeof bunFix.merged_at === "string" ? bunFix.merged_at : null,
		},
		// Automated source/issue observation can only request review. The incident becomes
		// permanent-validated after an official release passes the affected real terminal scenario.
		permanentStatus: "UNRESOLVED",
	};
}

export function stateChanged(previous: WatchState | null, current: WatchState): boolean {
	if (!previous) return true;
	return (
		previous.ompMainSha !== current.ompMainSha ||
		previous.ompLatestTag !== current.ompLatestTag ||
		previous.terminalSourceSha256 !== current.terminalSourceSha256 ||
		previous.terminalRegressionSha256 !== current.terminalRegressionSha256 ||
		previous.stdinEndIssue.state !== current.stdinEndIssue.state ||
		previous.stdinEndIssue.updatedAt !== current.stdinEndIssue.updatedAt ||
		previous.eintrIssue.state !== current.eintrIssue.state ||
		previous.eintrIssue.updatedAt !== current.eintrIssue.updatedAt ||
		previous.bunFix.state !== current.bunFix.state ||
		previous.bunFix.mergedAt !== current.bunFix.mergedAt
	);
}

export function statusMessage(state: WatchState, changed: boolean): { level: "info" | "warning" | "error"; text: string } {
	if (!state.bunEintrRetryShipped) {
		return {
			level: "error",
			text: `OMP watch: Bun ${state.bunVersion} predates the verified Darwin EINTR retry. Do not update or remove the local mitigation before review.`,
		};
	}
	if (changed) {
		return {
			level: "warning",
			text: `OMP upstream changed (${state.ompLatestTag}, main ${state.ompMainSha.slice(0, 8)}). Bun ${state.bunVersion} includes the EINTR retry, but stdin-ended/raw-mode remains unvalidated. Run “omp-concierge upstream-watch” before updating.`,
		};
	}
	return {
		level: "info",
		text: `OMP watch: Bun ${state.bunVersion} includes the Darwin EINTR retry; stdin-ended/raw-mode is still unresolved. Review is required before any OMP update.`,
	};
}

async function readState(path: string): Promise<WatchState | null> {
	try {
		const parsed = JSON.parse(await readFile(path, "utf8")) as WatchState;
		return parsed?.schema === 1 ? parsed : null;
	} catch {
		return null;
	}
}

async function writeState(path: string, state: WatchState): Promise<void> {
	await mkdir(dirname(path), { recursive: true });
	const temporary = `${path}.${process.pid}.tmp`;
	await writeFile(temporary, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
	await rename(temporary, path);
}

function isFresh(state: WatchState | null, now: number): boolean {
	if (!state) return false;
	const checkedAt = Date.parse(state.checkedAt);
	return Number.isFinite(checkedAt) && now - checkedAt < CHECK_INTERVAL_MS;
}

function notify(context: OmpContext, message: { level: "info" | "warning" | "error"; text: string }): void {
	if (!context.hasUI) return;
	try {
		context.ui?.notify(message.text, message.level);
	} catch {
		// Session replacement may invalidate ctx.ui while the background check finishes.
	}
}

export async function runStartupWatch(
	context: OmpContext,
	options: { statePath?: string; fetchImpl?: FetchLike; bunVersion?: string; now?: Date } = {},
): Promise<void> {
	const statePath = options.statePath ?? DEFAULT_STATE_PATH;
	const now = options.now ?? new Date();
	const previous = await readState(statePath);
	if (isFresh(previous, now.getTime())) {
		notify(context, statusMessage(previous!, false));
		return;
	}
	try {
		const current = await collectUpstreamState(options.fetchImpl, options.bunVersion ?? Bun.version, now);
		const changed = stateChanged(previous, current);
		await writeState(statePath, current);
		notify(context, statusMessage(current, changed));
	} catch (error) {
		const cached = previous ? ` Cached check: ${previous.checkedAt}.` : "";
		notify(context, {
			level: "warning",
			text: `OMP upstream-watch could not refresh; startup continues.${cached} ${String(error)}`,
		});
	}
}

export default function ompUpstreamWatch(api: OmpExtensionApi): void {
	api.on("session_start", (_event, context) => {
		// Deliberately off the critical startup path. Failure is reported in the UI and never aborts OMP.
		void runStartupWatch(context);
	});
}
