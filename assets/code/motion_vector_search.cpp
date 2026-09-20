#include <opencv2/opencv.hpp>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace std;
using namespace cv;
namespace fs = std::filesystem;

namespace {

const int kBlockSize = 16;
const int kSearchRange = 7;
const int kDefaultFramePairs = 30;
const vector<string> kMethods = {"exhaustive", "logarithmic", "hierarchical", "diamond"};

enum class RunMode {
    Sequence,
    Single
};

struct MotionVector {
    int dx;
    int dy;
};

struct BlockMatchResult {
    MotionVector mv;
    int sad;
    int searchedPoints;
};

struct FrameStats {
    string methodName;
    double psnr;
    long long totalSad;
    double avgSearchPoints;
    Mat compensatedFrame;
    Mat vectorMap;
    vector<vector<MotionVector>> motionVectors;
};

struct FrameComparisonRow {
    int frameIndex;
    FrameStats exhaustive;
    FrameStats logarithmic;
    FrameStats hierarchical;
    FrameStats diamond;
};

struct ProgramOptions {
    fs::path inputPath;
    fs::path outputPath;
    RunMode mode;
    int framePairs;
    int frameIndex;
};

static inline int clampInt(int value, int low, int high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}

bool ensureOutputDir(const fs::path& path) {
    try {
        if (!fs::exists(path)) {
            fs::create_directories(path);
        }
        return true;
    } catch (...) {
        return false;
    }
}

void saveImage(const fs::path& filename, const Mat& image) {
    if (!imwrite(filename.string(), image)) {
        cerr << "Failed to save image: " << filename.string() << endl;
    }
}

double computeMSE(const Mat& original, const Mat& reconstructed) {
    CV_Assert(original.size() == reconstructed.size());
    CV_Assert(original.type() == reconstructed.type());

    Mat diff;
    absdiff(original, reconstructed, diff);
    diff.convertTo(diff, CV_32F);
    diff = diff.mul(diff);
    Scalar total = sum(diff);
    return total[0] / static_cast<double>(original.total());
}

double computePSNR(const Mat& original, const Mat& reconstructed) {
    double mse = computeMSE(original, reconstructed);
    if (mse == 0.0) {
        return 99.0;
    }
    return 10.0 * log10((255.0 * 255.0) / mse);
}

bool hasImageExtension(const fs::path& path) {
    string extension = path.extension().string();
    transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char ch) {
        return static_cast<char>(tolower(ch));
    });

    return extension == ".png" || extension == ".jpg" || extension == ".jpeg" || extension == ".bmp" || extension == ".pgm";
}

vector<fs::path> collectInputImages(const fs::path& inputPath) {
    vector<fs::path> images;

    if (fs::is_regular_file(inputPath) && hasImageExtension(inputPath)) {
        images.push_back(inputPath);
        return images;
    }

    if (fs::is_directory(inputPath)) {
        for (const auto& entry : fs::directory_iterator(inputPath)) {
            if (entry.is_regular_file() && hasImageExtension(entry.path())) {
                images.push_back(entry.path());
            }
        }
        sort(images.begin(), images.end());
    }

    return images;
}

Mat loadGrayImage(const fs::path& imagePath) {
    return imread(imagePath.string(), IMREAD_GRAYSCALE);
}

bool parseInteger(const string& text, int& value) {
    try {
        size_t parsedLength = 0;
        int parsed = stoi(text, &parsedLength);
        if (parsedLength != text.size()) {
            return false;
        }
        value = parsed;
        return true;
    } catch (...) {
        return false;
    }
}

void printUsage(const char* exeName) {
    cout << "Usage:\n";
    cout << "  " << exeName << " <input_path> <output_path>\n";
    cout << "  " << exeName << " <input_path> <output_path> sequence <frame_pairs>\n";
    cout << "  " << exeName << " <input_path> <output_path> single <frame_index>\n\n";
    cout << "Fixed settings:\n";
    cout << "  block size   = " << kBlockSize << "\n";
    cout << "  search range = +/-" << kSearchRange << "\n";
}

bool parseArguments(int argc, char** argv, ProgramOptions& options) {
    options.inputPath = "input_image";
    options.outputPath = "output_image";
    options.mode = RunMode::Sequence;
    options.framePairs = kDefaultFramePairs;
    options.frameIndex = 1;

    if (argc >= 2) options.inputPath = argv[1];
    if (argc >= 3) options.outputPath = argv[2];

    if (argc == 1) {
        return true;
    }

    if (argc == 3) {
        return true;
    }

    if (argc >= 4) {
        string modeText = argv[3];
        if (modeText == "sequence") {
            options.mode = RunMode::Sequence;
            if (argc >= 5) {
                if (!parseInteger(argv[4], options.framePairs) || options.framePairs < 1) {
                    cerr << "Invalid frame_pairs: " << argv[4] << endl;
                    return false;
                }
            }
            if (argc > 5) {
                cerr << "Too many arguments for sequence mode." << endl;
                return false;
            }
            return true;
        }

        if (modeText == "single") {
            options.mode = RunMode::Single;
            if (argc != 5) {
                cerr << "Single mode requires frame_index." << endl;
                return false;
            }
            if (!parseInteger(argv[4], options.frameIndex)) {
                cerr << "Invalid frame index." << endl;
                return false;
            }
            if (options.frameIndex < 1) {
                cerr << "Single mode frame index must be at least 1." << endl;
                return false;
            }
            return true;
        }

        cerr << "Unknown mode: " << modeText << endl;
        return false;
    }

    return true;
}

int computeBlockSAD(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int candidateX,
    int candidateY,
    int blockSize
) {
    int sad = 0;

    for (int y = 0; y < blockSize; ++y) {
        for (int x = 0; x < blockSize; ++x) {
            int currentValue = current.at<uchar>(blockY + y, blockX + x);
            int referenceValue = reference.at<uchar>(candidateY + y, candidateX + x);
            sad += std::abs(currentValue - referenceValue);
        }
    }

    return sad;
}

bool isValidCandidate(const Mat& reference, int x, int y, int blockSize) {
    return x >= 0 && y >= 0 && x + blockSize <= reference.cols && y + blockSize <= reference.rows;
}

BlockMatchResult exhaustiveSearch(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int blockSize,
    int searchRange
) {
    BlockMatchResult best = {{0, 0}, std::numeric_limits<int>::max(), 0};

    for (int dy = -searchRange; dy <= searchRange; ++dy) {
        for (int dx = -searchRange; dx <= searchRange; ++dx) {
            int candidateX = blockX + dx;
            int candidateY = blockY + dy;

            if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
                continue;
            }

            int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
            ++best.searchedPoints;

            if (sad < best.sad) {
                best.mv = {dx, dy};
                best.sad = sad;
            }
        }
    }

    return best;
}

BlockMatchResult logarithmicSearch(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int blockSize,
    int searchRange
) {
    int centerDx = 0;
    int centerDy = 0;
    int step = 1;
    while (step < searchRange) {
        step <<= 1;
    }
    step >>= 1;
    if (step < 1) step = 1;

    BlockMatchResult best = {{0, 0}, std::numeric_limits<int>::max(), 0};

    while (step >= 1) {
        vector<Point> candidates = {
            Point(centerDx - step, centerDy - step),
            Point(centerDx,        centerDy - step),
            Point(centerDx + step, centerDy - step),
            Point(centerDx - step, centerDy),
            Point(centerDx,        centerDy),
            Point(centerDx + step, centerDy),
            Point(centerDx - step, centerDy + step),
            Point(centerDx,        centerDy + step),
            Point(centerDx + step, centerDy + step)
        };

        int localBestDx = centerDx;
        int localBestDy = centerDy;
        int localBestSad = std::numeric_limits<int>::max();
        bool localBestIsCenter = true;

        for (const Point& candidate : candidates) {
            if (std::abs(candidate.x) > searchRange || std::abs(candidate.y) > searchRange) {
                continue;
            }

            int candidateX = blockX + candidate.x;
            int candidateY = blockY + candidate.y;
            if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
                continue;
            }

            int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
            ++best.searchedPoints;

            if (sad < localBestSad) {
                localBestSad = sad;
                localBestDx = candidate.x;
                localBestDy = candidate.y;
                localBestIsCenter = (candidate.x == centerDx && candidate.y == centerDy);
            }
        }

        centerDx = localBestDx;
        centerDy = localBestDy;
        best.mv = {centerDx, centerDy};
        best.sad = localBestSad;

        if (localBestIsCenter && step > 1) {
            step /= 2;
        } else if (step == 1) {
            break;
        }
    }

    for (int dy = centerDy - 1; dy <= centerDy + 1; ++dy) {
        for (int dx = centerDx - 1; dx <= centerDx + 1; ++dx) {
            if (std::abs(dx) > searchRange || std::abs(dy) > searchRange) {
                continue;
            }

            int candidateX = blockX + dx;
            int candidateY = blockY + dy;
            if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
                continue;
            }

            int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
            ++best.searchedPoints;

            if (sad < best.sad) {
                best.mv = {dx, dy};
                best.sad = sad;
            }
        }
    }

    return best;
}

BlockMatchResult exhaustiveSearchAroundPredictor(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int blockSize,
    int searchRange,
    int predictorDx,
    int predictorDy,
    int refineRange
) {
    BlockMatchResult best = {{predictorDx, predictorDy}, std::numeric_limits<int>::max(), 0};

    for (int dy = predictorDy - refineRange; dy <= predictorDy + refineRange; ++dy) {
        for (int dx = predictorDx - refineRange; dx <= predictorDx + refineRange; ++dx) {
            if (std::abs(dx) > searchRange || std::abs(dy) > searchRange) {
                continue;
            }

            int candidateX = blockX + dx;
            int candidateY = blockY + dy;
            if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
                continue;
            }

            int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
            ++best.searchedPoints;

            if (sad < best.sad) {
                best.mv = {dx, dy};
                best.sad = sad;
            }
        }
    }

    return best;
}

BlockMatchResult hierarchicalSearch(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int blockSize,
    int searchRange
) {
    Mat currentSmall;
    Mat referenceSmall;
    pyrDown(current, currentSmall);
    pyrDown(reference, referenceSmall);

    int smallBlockX = blockX / 2;
    int smallBlockY = blockY / 2;
    int smallBlockSize = std::max(4, blockSize / 2);
    int smallSearchRange = std::max(1, searchRange / 2);

    BlockMatchResult coarse = exhaustiveSearch(
        currentSmall,
        referenceSmall,
        smallBlockX,
        smallBlockY,
        smallBlockSize,
        smallSearchRange
    );

    int predictorDx = coarse.mv.dx * 2;
    int predictorDy = coarse.mv.dy * 2;

    BlockMatchResult refined = exhaustiveSearchAroundPredictor(
        current,
        reference,
        blockX,
        blockY,
        blockSize,
        searchRange,
        predictorDx,
        predictorDy,
        2
    );

    refined.searchedPoints += coarse.searchedPoints;
    return refined;
}

BlockMatchResult diamondSearch(
    const Mat& current,
    const Mat& reference,
    int blockX,
    int blockY,
    int blockSize,
    int searchRange
) {
    const vector<Point> ldsp = {
        Point(0, 0),
        Point(0, -2),
        Point(-1, -1),
        Point(1, -1),
        Point(-2, 0),
        Point(2, 0),
        Point(-1, 1),
        Point(1, 1),
        Point(0, 2)
    };

    const vector<Point> sdsp = {
        Point(0, 0),
        Point(0, -1),
        Point(-1, 0),
        Point(1, 0),
        Point(0, 1)
    };

    int centerDx = 0;
    int centerDy = 0;
    BlockMatchResult best = {{0, 0}, std::numeric_limits<int>::max(), 0};

    while (true) {
        int localBestDx = centerDx;
        int localBestDy = centerDy;
        int localBestSad = std::numeric_limits<int>::max();

        for (const Point& offset : ldsp) {
            int dx = centerDx + offset.x;
            int dy = centerDy + offset.y;

            if (std::abs(dx) > searchRange || std::abs(dy) > searchRange) {
                continue;
            }

            int candidateX = blockX + dx;
            int candidateY = blockY + dy;
            if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
                continue;
            }

            int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
            ++best.searchedPoints;

            if (sad < localBestSad) {
                localBestSad = sad;
                localBestDx = dx;
                localBestDy = dy;
            }
        }

        centerDx = localBestDx;
        centerDy = localBestDy;

        if (centerDx == best.mv.dx && centerDy == best.mv.dy) {
            best.mv = {centerDx, centerDy};
            best.sad = localBestSad;
            break;
        }

        best.mv = {centerDx, centerDy};
        best.sad = localBestSad;
    }

    for (const Point& offset : sdsp) {
        int dx = centerDx + offset.x;
        int dy = centerDy + offset.y;

        if (std::abs(dx) > searchRange || std::abs(dy) > searchRange) {
            continue;
        }

        int candidateX = blockX + dx;
        int candidateY = blockY + dy;
        if (!isValidCandidate(reference, candidateX, candidateY, blockSize)) {
            continue;
        }

        int sad = computeBlockSAD(current, reference, blockX, blockY, candidateX, candidateY, blockSize);
        ++best.searchedPoints;

        if (sad < best.sad) {
            best.mv = {dx, dy};
            best.sad = sad;
        }
    }

    return best;
}

Mat buildCompensatedFrame(
    const Mat& reference,
    const vector<vector<MotionVector>>& motionVectors,
    int blockSize,
    Size frameSize
) {
    Mat compensated = Mat::zeros(frameSize, CV_8UC1);

    for (int blockRow = 0; blockRow < static_cast<int>(motionVectors.size()); ++blockRow) {
        for (int blockCol = 0; blockCol < static_cast<int>(motionVectors[blockRow].size()); ++blockCol) {
            int blockX = blockCol * blockSize;
            int blockY = blockRow * blockSize;
            int width = std::min(blockSize, frameSize.width - blockX);
            int height = std::min(blockSize, frameSize.height - blockY);

            MotionVector mv = motionVectors[blockRow][blockCol];
            int refX = clampInt(blockX + mv.dx, 0, reference.cols - width);
            int refY = clampInt(blockY + mv.dy, 0, reference.rows - height);

            Mat srcBlock = reference(Rect(refX, refY, width, height));
            srcBlock.copyTo(compensated(Rect(blockX, blockY, width, height)));
        }
    }

    return compensated;
}

Mat drawMotionVectorMap(
    const Mat& frame,
    const vector<vector<MotionVector>>& motionVectors,
    int blockSize
) {
    Mat canvas;
    cvtColor(frame, canvas, COLOR_GRAY2BGR);

    for (int blockRow = 0; blockRow < static_cast<int>(motionVectors.size()); ++blockRow) {
        for (int blockCol = 0; blockCol < static_cast<int>(motionVectors[blockRow].size()); ++blockCol) {
            int blockX = blockCol * blockSize;
            int blockY = blockRow * blockSize;
            int centerX = std::min(blockX + blockSize / 2, frame.cols - 1);
            int centerY = std::min(blockY + blockSize / 2, frame.rows - 1);

            MotionVector mv = motionVectors[blockRow][blockCol];
            Point start(centerX, centerY);
            Point end(centerX + mv.dx, centerY + mv.dy);

            arrowedLine(canvas, start, end, Scalar(0, 0, 255), 1, LINE_AA, 0, 0.25);
            rectangle(canvas, Rect(blockX, blockY, std::min(blockSize, frame.cols - blockX), std::min(blockSize, frame.rows - blockY)), Scalar(0, 255, 0), 1);
        }
    }

    return canvas;
}

FrameStats processFramePair(
    const Mat& current,
    const Mat& reference,
    const string& methodName
) {
    FrameStats stats;
    stats.methodName = methodName;
    stats.totalSad = 0;
    long long totalSearchPoints = 0;

    int blockRows = (current.rows + kBlockSize - 1) / kBlockSize;
    int blockCols = (current.cols + kBlockSize - 1) / kBlockSize;
    stats.motionVectors.assign(blockRows, vector<MotionVector>(blockCols, {0, 0}));

    for (int blockY = 0, blockRow = 0; blockY + kBlockSize <= current.rows; blockY += kBlockSize, ++blockRow) {
        for (int blockX = 0, blockCol = 0; blockX + kBlockSize <= current.cols; blockX += kBlockSize, ++blockCol) {
            BlockMatchResult result;

            if (methodName == "exhaustive") {
                result = exhaustiveSearch(current, reference, blockX, blockY, kBlockSize, kSearchRange);
            } else if (methodName == "logarithmic") {
                result = logarithmicSearch(current, reference, blockX, blockY, kBlockSize, kSearchRange);
            } else if (methodName == "diamond") {
                result = diamondSearch(current, reference, blockX, blockY, kBlockSize, kSearchRange);
            } else {
                result = hierarchicalSearch(current, reference, blockX, blockY, kBlockSize, kSearchRange);
            }

            stats.motionVectors[blockRow][blockCol] = result.mv;
            stats.totalSad += result.sad;
            totalSearchPoints += result.searchedPoints;
        }
    }

    int totalBlocks = 0;
    for (int blockY = 0; blockY + kBlockSize <= current.rows; blockY += kBlockSize) {
        for (int blockX = 0; blockX + kBlockSize <= current.cols; blockX += kBlockSize) {
            ++totalBlocks;
        }
    }

    stats.compensatedFrame = buildCompensatedFrame(reference, stats.motionVectors, kBlockSize, current.size());
    stats.vectorMap = drawMotionVectorMap(current, stats.motionVectors, kBlockSize);
    stats.psnr = computePSNR(current, stats.compensatedFrame);
    stats.avgSearchPoints = (totalBlocks > 0) ? static_cast<double>(totalSearchPoints) / totalBlocks : 0.0;
    return stats;
}

void saveFrameStats(const fs::path& outputDir, const FrameStats& stats, int frameIndex) {
    fs::path frameDir = outputDir / stats.methodName;
    ensureOutputDir(frameDir);

    string indexText = to_string(frameIndex);
    saveImage(frameDir / ("compensated_frame_" + indexText + ".png"), stats.compensatedFrame);
    saveImage(frameDir / ("motion_vector_" + indexText + ".png"), stats.vectorMap);
}

void appendCsvRow(ofstream& csv, int frameIndex, const FrameStats& stats) {
    csv << frameIndex << ","
        << stats.methodName << ","
        << fixed << setprecision(4) << stats.psnr << ","
        << stats.totalSad << ","
        << fixed << setprecision(4) << stats.avgSearchPoints << "\n";
}

void writeWideCsvHeader(ofstream& csv) {
    csv << "frame_index,"
        << "exhaustive_psnr,logarithmic_psnr,hierarchical_psnr,diamond_psnr,"
        << "exhaustive_sad,logarithmic_sad,hierarchical_sad,diamond_sad,"
        << "exhaustive_avg_search,logarithmic_avg_search,hierarchical_avg_search,diamond_avg_search\n";
}

void appendWideCsvRow(ofstream& csv, const FrameComparisonRow& row) {
    csv << row.frameIndex << ","
        << fixed << setprecision(4)
        << row.exhaustive.psnr << ","
        << row.logarithmic.psnr << ","
        << row.hierarchical.psnr << ","
        << row.diamond.psnr << ","
        << row.exhaustive.totalSad << ","
        << row.logarithmic.totalSad << ","
        << row.hierarchical.totalSad << ","
        << row.diamond.totalSad << ","
        << row.exhaustive.avgSearchPoints << ","
        << row.logarithmic.avgSearchPoints << ","
        << row.hierarchical.avgSearchPoints << ","
        << row.diamond.avgSearchPoints << "\n";
}

bool loadFramePair(
    const vector<fs::path>& images,
    int referenceIndex,
    int currentIndex,
    Mat& reference,
    Mat& current,
    const string& errorContext
) {
    reference = loadGrayImage(images[referenceIndex]);
    current = loadGrayImage(images[currentIndex]);

    if (reference.empty() || current.empty()) {
        cerr << "Failed to read " << errorContext << ": "
             << images[referenceIndex].string() << " and " << images[currentIndex].string() << endl;
        return false;
    }

    if (reference.size() != current.size()) {
        cerr << "Frame size mismatch for " << errorContext << ": "
             << images[referenceIndex].string() << " and " << images[currentIndex].string() << endl;
        return false;
    }

    return true;
}

FrameComparisonRow runAllMethods(
    const Mat& current,
    const Mat& reference,
    const fs::path& outputRoot,
    ofstream& csv,
    int frameIndex
) {
    FrameComparisonRow row;
    row.frameIndex = frameIndex;

    for (const string& method : kMethods) {
        FrameStats stats = processFramePair(current, reference, method);
        saveFrameStats(outputRoot, stats, frameIndex);
        appendCsvRow(csv, frameIndex, stats);

        if (method == "exhaustive") {
            row.exhaustive = stats;
        } else if (method == "logarithmic") {
            row.logarithmic = stats;
        } else if (method == "diamond") {
            row.diamond = stats;
        } else {
            row.hierarchical = stats;
        }

        cout << "  [" << method << "]"
             << " PSNR=" << fixed << setprecision(4) << stats.psnr
             << " dB, total SAD=" << stats.totalSad
             << ", avg search points=" << stats.avgSearchPoints << endl;
    }

    return row;
}

void processSequence(
    const vector<fs::path>& images,
    const fs::path& outputRoot,
    int maxFrames
) {
    ofstream csv((outputRoot / "metrics.csv").string());
    ofstream wideCsv((outputRoot / "metrics_wide.csv").string());
    csv << "frame_index,method,psnr,total_sad,avg_search_points\n";
    writeWideCsvHeader(wideCsv);

    int framePairs = std::min(static_cast<int>(images.size()) - 1, maxFrames);
    for (int i = 1; i <= framePairs; ++i) {
        Mat reference;
        Mat current;
        if (!loadFramePair(images, i - 1, i, reference, current, "frame pair")) {
            continue;
        }

        cout << "\nProcessing frame pair " << i - 1 << " -> " << i << endl;
        FrameComparisonRow row = runAllMethods(current, reference, outputRoot, csv, i);
        appendWideCsvRow(wideCsv, row);
    }
}

void processSingleFrame(
    const vector<fs::path>& images,
    const fs::path& outputRoot,
    int frameIndex
) {
    int referenceIndex = frameIndex - 1;
    int currentIndex = frameIndex;

    if (frameIndex < 1) {
        cerr << "Frame index must be at least 1." << endl;
        return;
    }

    if (referenceIndex >= static_cast<int>(images.size()) || currentIndex >= static_cast<int>(images.size())) {
        cerr << "Frame index out of range. Total images: " << images.size() << endl;
        return;
    }

    Mat reference;
    Mat current;
    if (!loadFramePair(images, referenceIndex, currentIndex, reference, current, "selected frames")) {
        return;
    }

    ofstream csv((outputRoot / "metrics_single.csv").string());
    csv << "frame_index,method,psnr,total_sad,avg_search_points\n";

    cout << "Processing single frame comparison " << referenceIndex << " -> " << currentIndex << endl;
    runAllMethods(current, reference, outputRoot, csv, currentIndex);
}

}  // namespace

int main(int argc, char** argv) {
    ProgramOptions options;
    if (!parseArguments(argc, argv, options)) {
        printUsage(argv[0]);
        return -1;
    }

    if (!fs::exists(options.inputPath)) {
        cerr << "Input path does not exist: " << options.inputPath.string() << endl;
        return -1;
    }

    if (!ensureOutputDir(options.outputPath)) {
        cerr << "Cannot create output directory: " << options.outputPath.string() << endl;
        return -1;
    }

    vector<fs::path> images = collectInputImages(options.inputPath);
    if (images.size() < 2) {
        cerr << "Need at least 2 images for motion estimation: " << options.inputPath.string() << endl;
        return -1;
    }

    cout << "Found " << images.size() << " image(s)." << endl;
    cout << "Block size: " << kBlockSize << endl;
    cout << "Search range: +/-" << kSearchRange << endl;

    fs::path runOutputPath;
    if (options.mode == RunMode::Single) {
        runOutputPath = options.outputPath / "single" / to_string(options.frameIndex);
        ensureOutputDir(runOutputPath);
        cout << "Mode: single frame " << options.frameIndex << endl;
        cout << "Output folder: " << runOutputPath.string() << endl;
        processSingleFrame(images, runOutputPath, options.frameIndex);
    } else {
        runOutputPath = options.outputPath / "sequence";
        ensureOutputDir(runOutputPath);
        cout << "Mode: sequence" << endl;
        cout << "Max frame pairs: " << options.framePairs << endl;
        cout << "Output folder: " << runOutputPath.string() << endl;
        processSequence(images, runOutputPath, options.framePairs);
    }

    cout << "\nDone. Check output folder: " << runOutputPath.string() << endl;
    return 0;
}
