from logger import app_logger, log_listeners


def main():
    app_logger.debug("This is a DEBUG message.")
    app_logger.info("This is an INFO message.")
    app_logger.warning("This is a WARNING message.")
    app_logger.error("This is an ERROR message.")
    app_logger.critical("This is a CRITICAL message.")
    # After finishing with logging
    for listener in log_listeners:
        listener.stop()

if __name__ == "__main__":
    
    main()
