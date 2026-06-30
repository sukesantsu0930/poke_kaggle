def main():
    try:
        import torch
    except ImportError:
        print("torch_importable=False")
        return

    print(f"torch_importable=True")
    print(f"torch_version={torch.__version__}")
    print(f"cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"cuda_device_count={torch.cuda.device_count()}")
        for index in range(torch.cuda.device_count()):
            print(f"cuda_device_{index}={torch.cuda.get_device_name(index)}")


if __name__ == "__main__":
    main()
